"""Candidate timeline (B.2): one row per event, idempotent-retry safety, ordering,
event_type filter, tenant isolation, staff/client gates. Append-only REVOKE is
proven on dev RDS (local runs as postgres master), not here."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Interview, Offer, Submission, Job,
)

HOST = {"host": "spstechnosoft.com"}
PW = "TimelineLocal!123"
RECRUITER = "tl-rec@local.test"


def _mk_user(db, tenant, email, roles):
    # leftover-robust: delete a prior user's memberships/client bindings first
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="TL Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    rec = _mk_user(db, sps, RECRUITER, ["recruiter"])
    yield sps
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    for M in (Interview, Offer, Submission, Application, Job, Candidate):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _chain(c):
    """job + candidate + application; returns (cand_id, app_id)."""
    job = c.post("/api/jobs", json={"title": "TL Engineer"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Timeline Cand",
                                           "phone": "9855501234"}, headers=HOST).json()
    appn = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                  headers=HOST).json()
    return cand["id"], appn["id"]


def _timeline(c, cid, **params):
    r = c.get(f"/api/candidates/{cid}/timeline", headers=HOST, params=params or None)
    assert r.status_code == 200, r.text
    return r.json()


def test_application_and_stage_change_emit(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _chain(c)
    assert c.patch(f"/api/applications/{aid}/stage", json={"stage": "screening"},
                   headers=HOST).status_code == 200
    events = _timeline(c, cid)
    types = [e["event_type"] for e in events]
    assert types == ["Application", "StageChange"]        # chronological, oldest first
    stage = events[-1]["payload"]
    assert stage["from"] == "applied" and stage["to"] == "screening" and stage["application_id"] == aid


def test_submission_offer_interview_emit(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _chain(c)
    assert c.post(f"/api/applications/{aid}/submissions", headers=HOST).status_code == 200
    assert c.post(f"/api/applications/{aid}/offers", json={"ctc": 1200000},
                  headers=HOST).status_code == 200
    assert c.post(f"/api/applications/{aid}/interviews", json={"mode": "video"},
                  headers=HOST).status_code == 200
    types = [e["event_type"] for e in _timeline(c, cid)]
    assert types == ["Application", "Submission", "Offer", "Interview"]


def test_idempotent_retry_appends_exactly_once(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _chain(c)
    key = f"tl-idem-{uuid.uuid4()}"
    h = {**HOST, "Idempotency-Key": key}
    r1 = c.post(f"/api/applications/{aid}/submissions", headers=h)
    r2 = c.post(f"/api/applications/{aid}/submissions", headers=h)   # replay
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]                        # cached result
    subs = [e for e in _timeline(c, cid) if e["event_type"] == "Submission"]
    assert len(subs) == 1, "idempotent retry double-appended a timeline row"


def test_event_type_filter(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _chain(c)
    c.patch(f"/api/applications/{aid}/stage", json={"stage": "screening"}, headers=HOST)
    only = _timeline(c, cid, event_type="StageChange")
    assert len(only) == 1 and only[0]["event_type"] == "StageChange"


def test_registration_emits_timeline(env):
    c = TestClient(app)
    r = c.post("/api/register/candidate", json={
        "full_name": "Reg Timeline", "email": "reg-tl@local.test", "phone": "9855509999",
        "pan": "REGTL1234K", "captcha_token": "test-token",
        "consent_data_processing": True}, headers=HOST)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    sc = TestClient(app); _login(sc, RECRUITER)
    events = _timeline(sc, cid)
    assert [e["event_type"] for e in events] == ["Registration"]
    assert events[0]["payload"] == {"source": "self_registration"}
    # cleanup consent rows created by registration
    db = get_sessionmaker()()
    db.execute(delete(Consent).where(Consent.subject_candidate_id == uuid.UUID(cid)))
    db.commit(); db.close()


def test_tenant_isolation_404(env):
    db = get_sessionmaker()()
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB4")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB4", slug="testb4", name="Tenant B4"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
    cand_b = Candidate(tenant_id=tb.id, full_name="B4 Person"); db.add(cand_b); db.commit()
    try:
        c = TestClient(app); _login(c, RECRUITER)  # SPS001 staff
        r = c.get(f"/api/candidates/{cand_b.id}/timeline", headers=HOST)
        assert r.status_code == 404, "LEAK: tenant A staff read tenant B timeline"
    finally:
        db.execute(delete(Candidate).where(Candidate.tenant_id == tb.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit(); db.close()


def test_candidate_role_403(env):
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk_user(db, sps, "tl-cand-role@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "tl-cand-role@local.test")
        r = c.get(f"/api/candidates/{uuid.uuid4()}/timeline", headers=HOST)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def test_client_session_403(env):
    """A client-portal session (client_id bound in the JWT) must NOT read a
    candidate's internal timeline — same hardening as the staff endpoints."""
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="TL ClientCo")
    db.add(client); db.flush()
    cu_user = User(tenant_id=sps.id, email="tl-client@local.test",
                   password_hash=PasswordHasher().hash(PW), full_name="TL Client", status="active")
    db.add(cu_user); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=cu_user.id, client_id=client.id, status="active"))
    cand = Candidate(tenant_id=sps.id, full_name="TL Internal Cand")
    db.add(cand); db.commit()
    try:
        c = TestClient(app); _login(c, "tl-client@local.test")
        r = c.get(f"/api/candidates/{cand.id}/timeline", headers=HOST)
        assert r.status_code == 403, "LEAK: client session read an internal candidate timeline"
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == cu_user.id))
        db.execute(delete(User).where(User.id == cu_user.id))
        db.execute(delete(Candidate).where(Candidate.id == cand.id))
        db.execute(delete(Client).where(Client.id == client.id))
        db.commit(); db.close()
