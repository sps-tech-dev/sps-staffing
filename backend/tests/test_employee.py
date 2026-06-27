"""Employee SLA hub: staff-gated, returns scoped queue + SLA."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job

HOST = {"host": "spstechnosoft.com"}
PW = "EmpLocal!123"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Emp", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def recruiter():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "emp@local.test", ["recruiter"])
    yield
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def test_overview_staff_only_and_sla(recruiter):
    c = TestClient(app); _login(c, "emp@local.test")
    job = c.post("/api/jobs", json={"title": "Data Engineer"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Asha Sharma"}, headers=HOST).json()
    c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST)
    r = c.get("/api/employee/overview", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["open"] >= 1
    item = body["queue"][0]
    assert {"id", "candidate", "job", "stage", "ageHours", "sla"} <= item.keys()
    assert item["sla"] == "ok"  # just created → within SLA


def test_overview_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "cand-emp@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "cand-emp@local.test")
        assert c.get("/api/employee/overview", headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
