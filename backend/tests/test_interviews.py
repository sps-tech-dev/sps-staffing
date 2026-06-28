"""Interviews: schedule against application, reschedule + outcome, staff-gate."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Interview, Job

HOST = {"host": "spstechnosoft.com"}
PW = "IvLocal!123"
EMAIL = "iv@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Iv", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def recruiter():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, EMAIL, ["recruiter"])
    yield sps
    db.execute(delete(Interview).where(Interview.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def _seed_app(c):
    job = c.post("/api/jobs", json={"title": "QA Lead"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Meera Iyer"}, headers=HOST).json()
    return c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()["id"]


def test_schedule_and_outcome(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    iv = c.post(f"/api/applications/{app_id}/interviews",
                json={"scheduled_at": "2026-07-10T10:30:00+00:00", "mode": "video", "interviewer_name": "Priya"}, headers=HOST)
    assert iv.status_code == 200, iv.text
    iid = iv.json()["id"]
    assert iv.json()["mode"] == "video" and iv.json()["status"] == "scheduled"

    upd = c.patch(f"/api/interviews/{iid}", json={"status": "completed", "feedback": "Strong system design"}, headers=HOST)
    assert upd.status_code == 200 and upd.json()["status"] == "completed"
    assert upd.json()["feedback"] == "Strong system design"

    row = next(i for i in c.get("/api/interviews", headers=HOST).json() if i["id"] == iid)
    assert row["candidate"] == "Meera Iyer" and row["job"] == "QA Lead"
    assert any(i["id"] == iid for i in c.get(f"/api/applications/{app_id}/interviews", headers=HOST).json())


def test_bad_mode_and_status_422(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    assert c.post(f"/api/applications/{app_id}/interviews", json={"mode": "telepathy"}, headers=HOST).status_code == 422
    iid = c.post(f"/api/applications/{app_id}/interviews", json={}, headers=HOST).json()["id"]
    assert c.patch(f"/api/interviews/{iid}", json={"status": "ghosted"}, headers=HOST).status_code == 422


def test_interview_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "iv-cand@local.test", ["candidate"])
    try:
        import uuid
        c = TestClient(app); _login(c, "iv-cand@local.test")
        assert c.post(f"/api/applications/{uuid.uuid4()}/interviews", json={}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
