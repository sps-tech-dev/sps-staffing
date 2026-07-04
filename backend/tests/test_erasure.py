"""DPDP erasure Stage 1: disable-on-request, anonymize-on-approval (incl. blind-index
clearing), retention of de-identified records, audit, legal-hold gate, purge stub."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app import erasure
from app.crypto import blind_index
from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, BusinessUnit, Consent, DpdpRequest, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job

HOST = {"host": "spstechnosoft.com"}
PW = "EraseLocal!123"
EMAIL = "erase@local.test"
ADMIN = "erase-admin@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Erase Subject", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


def _seed_candidate(db, sps, email):
    cand = Candidate(tenant_id=sps.id, full_name="Erase Subject", email=email,
                     phone_enc="9876543210", pan_enc="ERASE1234Z",
                     phone_bidx=blind_index("9876543210"), pan_bidx=blind_index("ERASE1234Z"),
                     source="self_registration"); db.add(cand); db.flush()
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Analyst"); db.add(job); db.flush()
    db.add(Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, stage="applied"))
    db.add(Consent(tenant_id=sps.id, subject_candidate_id=cand.id, purpose="data_processing",
                   granted=True, policy_version="p")); db.commit()
    return cand.id


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, EMAIL, ["candidate"])
    admin = _mk(db, sps, ADMIN, ["admin"])
    yield sps, u, admin
    for uid in (u.id, admin.id):
        db.execute(delete(Membership).where(Membership.user_id == uid))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    db.execute(delete(DpdpRequest).where(DpdpRequest.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(User).where(User.id.in_([u.id, admin.id]))); db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def _cand_raw(cid):
    db = get_sessionmaker()()
    row = db.execute(text("SELECT full_name, email, phone_enc, pan_enc, phone_bidx, pan_bidx, "
                          "search_doc, source, deleted_at FROM staffing.candidates WHERE id=:i"),
                     {"i": cid}).one()
    db.close()
    return row


def test_normal_erasure_anonymizes_retains_and_audits(env):
    sps, u, _ = env
    cid = _seed_candidate(get_sessionmaker()(), sps, EMAIL)
    c = TestClient(app); _login(c, EMAIL)
    r = c.post("/api/privacy/erase", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed" and body["candidates_disabled"] == 1
    assert body["summary"]["blind_indexes_cleared"] is True

    fn, email, ph_enc, pan_enc, ph_bidx, pan_bidx, sdoc, src, deleted = _cand_raw(cid)
    assert fn == "[erased]" and email is None
    assert ph_enc is None and pan_enc is None
    assert ph_bidx is None and pan_bidx is None          # CRITICAL: pseudonymous IDs cleared
    assert sdoc is None and src is None
    assert deleted is not None                            # soft-deleted

    db = get_sessionmaker()()
    # de-identified application RETAINED
    assert db.execute(select(Application).where(Application.candidate_id == cid)).scalars().all()
    # consents + audit RETAINED (untouched)
    assert db.execute(select(Consent).where(Consent.subject_candidate_id == cid)).scalars().all()
    assert db.execute(select(AuditLog).where(AuditLog.tenant_id == sps.id,
                      AuditLog.action == "dpdp.erasure_executed")).scalars().first() is not None
    # user disabled + anonymized (not hard-deleted)
    usr = db.get(User, u.id)
    assert usr is not None and usr.status == "erased" and usr.full_name == "[erased]"
    assert usr.email != EMAIL and usr.password_hash == "!erased"
    db.close()


def test_legal_hold_disables_but_does_not_anonymize_until_approved(env, monkeypatch):
    sps, u, admin = env
    cid = _seed_candidate(get_sessionmaker()(), sps, EMAIL)
    monkeypatch.setattr(erasure, "under_legal_hold", lambda db, ctx, user: True)

    c = TestClient(app); _login(c, EMAIL)
    r = c.post("/api/privacy/erase", headers=HOST).json()
    assert r["status"] == "legal_hold" and r["legal_hold"] is True
    assert r["candidates_disabled"] == 1

    # disabled (soft-deleted) but NOT anonymized — PII + blind index intact
    fn, email, ph_enc, _pe, ph_bidx, _pb, _sd, _sr, deleted = _cand_raw(cid)
    assert deleted is not None                            # disabled immediately
    assert fn == "Erase Subject" and email == EMAIL       # NOT anonymized
    assert ph_bidx is not None                            # blind index still present

    # explicit manual approval by admin → now anonymized
    req_id = r["request_id"]
    ac = TestClient(app); _login(ac, ADMIN)
    appr = ac.post(f"/api/admin/erasure-requests/{req_id}/approve", headers=HOST)
    assert appr.status_code == 200, appr.text
    assert appr.json()["status"] == "completed"
    fn2, email2, _pe2, _pa2, ph_bidx2, _pb2, _s2, _sr2, _d2 = _cand_raw(cid)
    assert fn2 == "[erased]" and email2 is None and ph_bidx2 is None


def test_admin_can_reject(env):
    sps, u, admin = env
    _seed_candidate(get_sessionmaker()(), sps, EMAIL)
    # create a held request to reject (so it isn't auto-completed)
    db = get_sessionmaker()()
    req = DpdpRequest(tenant_id=sps.id, subject_user_id=u.id, kind="erasure",
                      status="legal_hold", legal_hold=True); db.add(req); db.commit()
    rid = str(req.id); db.close()
    ac = TestClient(app); _login(ac, ADMIN)
    assert ac.post(f"/api/admin/erasure-requests/{rid}/reject", headers=HOST).json()["status"] == "rejected"


def test_auto_purge_is_a_noop_stub():
    db = get_sessionmaker()()
    assert erasure.auto_purge_due_requests(db) == 0   # deletes nothing; retention period unset
    db.close()


def test_erasure_requires_approved_transition(env):
    """run_erasure must refuse if the request isn't approved (the gate)."""
    sps, u, _ = env
    db = get_sessionmaker()()
    req = DpdpRequest(tenant_id=sps.id, subject_user_id=u.id, kind="erasure", status="pending")
    db.add(req); db.flush()
    from app.context import RequestContext
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="STAFFING", user_id=str(u.id))
    with pytest.raises(ValueError):
        erasure.run_erasure(db, ctx, req, db.get(User, u.id))
    db.rollback(); db.close()