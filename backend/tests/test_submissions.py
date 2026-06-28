"""Submissions: submit to client, feedback/status, tenant isolation."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job, Submission

HOST = {"host": "spstechnosoft.com"}
PW = "SubLocal!123"
EMAIL = "sub@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Sub", status="active"); db.add(u); db.flush()
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
    db.execute(delete(Submission).where(Submission.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def _seed_app(c):
    job = c.post("/api/jobs", json={"title": "Backend Engineer"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Asha Rao"}, headers=HOST).json()
    appn = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()
    return appn["id"]


def test_submit_feedback_and_dashboard(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    sub = c.post(f"/api/applications/{app_id}/submissions", headers=HOST)
    assert sub.status_code == 200, sub.text
    sid = sub.json()["id"]
    assert sub.json()["status"] == "submitted"

    # client feedback + status
    upd = c.patch(f"/api/submissions/{sid}", json={"status": "shortlisted", "client_feedback": "Strong fit"}, headers=HOST)
    assert upd.status_code == 200 and upd.json()["status"] == "shortlisted"
    assert upd.json()["client_feedback"] == "Strong fit"

    # dashboard list carries candidate + job names
    rows = c.get("/api/submissions", headers=HOST).json()
    row = next(r for r in rows if r["id"] == sid)
    assert row["candidate"] == "Asha Rao" and row["job"] == "Backend Engineer"

    # per-application list
    assert any(s["id"] == sid for s in c.get(f"/api/applications/{app_id}/submissions", headers=HOST).json())


def test_bad_status_rejected(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    sid = c.post(f"/api/applications/{app_id}/submissions", headers=HOST).json()["id"]
    assert c.patch(f"/api/submissions/{sid}", json={"status": "bogus"}, headers=HOST).status_code == 422


def test_submission_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "sub-cand@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "sub-cand@local.test")
        import uuid
        r = c.post(f"/api/applications/{uuid.uuid4()}/submissions", headers=HOST)
        assert r.status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
