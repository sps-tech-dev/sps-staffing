"""DPDP self-service: consent ledger, data export, erasure request (F6)."""
from __future__ import annotations

import json

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, BusinessUnit, Consent, DpdpRequest, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job

HOST = {"host": "spstechnosoft.com"}
PW = "PrivLocal!123"
EMAIL = "priv@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Priv Subject", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def subject():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, EMAIL, ["candidate"])
    yield sps, u
    db.execute(delete(Consent).where(Consent.subject_user_id == u.id))
    db.execute(delete(DpdpRequest).where(DpdpRequest.subject_user_id == u.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def test_consent_requires_auth():
    c = TestClient(app)
    assert c.get("/api/privacy/consent", headers=HOST).status_code == 401


def test_consent_set_and_latest_wins(subject):
    c = TestClient(app); _login(c)
    # default: nothing granted
    r = c.get("/api/privacy/consent", headers=HOST).json()
    assert r["purposes"]["marketing"] is False
    assert r["policy_version"]
    # grant marketing
    assert c.post("/api/privacy/consent", json={"purpose": "marketing", "granted": True}, headers=HOST).status_code == 200
    assert c.get("/api/privacy/consent", headers=HOST).json()["purposes"]["marketing"] is True
    # withdraw — latest event wins
    assert c.post("/api/privacy/consent", json={"purpose": "marketing", "granted": False}, headers=HOST).status_code == 200
    assert c.get("/api/privacy/consent", headers=HOST).json()["purposes"]["marketing"] is False


def test_consent_rejects_unknown_purpose(subject):
    c = TestClient(app); _login(c)
    assert c.post("/api/privacy/consent", json={"purpose": "tracking", "granted": True}, headers=HOST).status_code == 422


def test_export_includes_own_decrypted_pii_and_audits(subject):
    sps, u = subject
    # a candidate sharing the subject's email (with ENCRYPTED PII) + an application
    db = get_sessionmaker()()
    cand = Candidate(tenant_id=sps.id, full_name="Priv Subject", email=EMAIL,
                     phone_enc="9876500011", pan_enc="PRIVA1234Z"); db.add(cand); db.flush()
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Analyst"); db.add(job); db.flush()
    db.add(Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, stage="sourced")); db.commit(); db.close()

    c = TestClient(app); _login(c)
    r = c.post("/api/privacy/export", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "export" and body["status"] == "completed"
    assert body["data"]["account"]["email"] == EMAIL
    assert len(body["data"]["candidates"]) == 1
    assert len(body["data"]["applications"]) == 1
    # the principal's OWN PII is decrypted in the bundle
    cd = body["data"]["candidates"][0]
    assert cd["phone"] == "9876500011" and cd["pan"] == "PRIVA1234Z"

    # privileged disclosure was audited (who/when + pii flag)
    db = get_sessionmaker()()
    audit = db.execute(
        select(AuditLog).where(AuditLog.tenant_id == sps.id, AuditLog.action == "dpdp.export")
        .order_by(AuditLog.ts.desc())
    ).scalars().first()
    assert audit is not None and audit.actor_id == u.id
    assert audit.after and audit.after.get("pii_disclosed") is True
    db.close()


def test_export_isolation_only_own_pii(subject):
    """Principal A's export contains A's PII and ZERO of principal B's — the
    isolation assertion, now with decryption in the path."""
    sps, u = subject  # principal A = EMAIL
    db = get_sessionmaker()()
    db.add(Candidate(tenant_id=sps.id, full_name="A Person", email=EMAIL,
                     phone_enc="9000000001", pan_enc="AAAAA1111A"))
    b = _mk(db, sps, "privb@local.test", ["candidate"])
    db.add(Candidate(tenant_id=sps.id, full_name="B Person", email="privb@local.test",
                     phone_enc="9000000002", pan_enc="BBBBB2222B"))
    db.commit(); db.close()

    c = TestClient(app); _login(c)  # logged in as A
    body = c.post("/api/privacy/export", headers=HOST).json()
    blob = json.dumps(body)
    assert "9000000001" in blob and "AAAAA1111A" in blob          # A's PII present
    assert "9000000002" not in blob and "BBBBB2222B" not in blob  # B's PII absent
    assert all(cd["email"] == EMAIL for cd in body["data"]["candidates"])

    db = get_sessionmaker()()
    db.execute(delete(Consent).where(Consent.subject_user_id == b.id))
    db.execute(delete(Membership).where(Membership.user_id == b.id))
    db.execute(delete(User).where(User.id == b.id)); db.commit(); db.close()


def test_erasure_request_auto_completes_stage1(subject):
    # Stage 1: a normal erasure auto-approves → completed (full anonymize flow is
    # covered in test_erasure.py). Here just confirm the request is recorded + final.
    c = TestClient(app); _login(c)
    r = c.post("/api/privacy/erase", headers=HOST)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "erasure" and r.json()["status"] == "completed"
    items = c.get("/api/privacy/requests", headers=HOST).json()["items"]
    assert any(i["kind"] == "erasure" for i in items)
