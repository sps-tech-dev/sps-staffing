"""Staffing endpoints: role gate, pipeline-stage rules, cross-tenant isolation."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Client, Job

HOST = {"host": "spstechnosoft.com"}  # → owner tenant SPS001
PW = "StaffLocal!123"


def _mk_user(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Test User", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def recruiter():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk_user(db, sps, "recruiter@local.test", ["recruiter"])
    yield
    # cleanup staffing rows + the user
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=host).status_code == 200


def test_staff_create_list_job(recruiter):
    c = TestClient(app); _login(c, "recruiter@local.test")
    j = c.post("/api/jobs", json={"title": "PySpark Data Engineer"}, headers=HOST)
    assert j.status_code == 200, j.text
    jid = j.json()["id"]
    listing = c.get("/api/jobs", headers=HOST).json()
    assert any(x["id"] == jid for x in listing)


def test_illegal_stage_transition_409(recruiter):
    c = TestClient(app); _login(c, "recruiter@local.test")
    job = c.post("/api/jobs", json={"title": "Backend Engineer"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Asha Sharma", "email": "asha@x.com",
                                           "phone": "9876543210"}, headers=HOST).json()
    appn = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()
    assert appn["stage"] == "applied"
    ok = c.patch(f"/api/applications/{appn['id']}/stage", json={"stage": "screening"}, headers=HOST)
    assert ok.status_code == 200 and ok.json()["stage"] == "screening"
    bad = c.patch(f"/api/applications/{appn['id']}/stage", json={"stage": "joined"}, headers=HOST)
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "ILLEGAL_TRANSITION"


def test_candidate_role_cannot_create_job_403():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk_user(db, sps, "cand-role@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "cand-role@local.test")
        r = c.post("/api/jobs", json={"title": "X"}, headers=HOST)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def test_cross_tenant_job_isolation(recruiter):
    # Tenant A (SPS001) recruiter creates a job.
    ca = TestClient(app); _login(ca, "recruiter@local.test")
    a_job = ca.post("/api/jobs", json={"title": "A-only Job"}, headers=HOST).json()["id"]
    # Tenant B with its own staff user + subdomain host.
    db = get_sessionmaker()()
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB2")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB2", slug="testb2", name="Tenant B2"); db.add(tb); db.flush()
        bu = BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing"); db.add(bu); db.flush()
    ub = _mk_user(db, tb, "rec@testb2.local", ["recruiter"])
    B_HOST = {"host": "testb2.spstechnosoft.com"}  # subdomain → tenant B
    try:
        cb = TestClient(app); _login(cb, "rec@testb2.local", B_HOST)
        jobs_b = cb.get("/api/jobs", headers=B_HOST).json()
        assert all(x["id"] != a_job for x in jobs_b), "LEAK: tenant B sees tenant A's job"
    finally:
        db.execute(delete(Application).where(Application.tenant_id == tb.id))
        db.execute(delete(Job).where(Job.tenant_id == tb.id))
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit(); db.close()
