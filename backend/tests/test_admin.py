"""Admin console: admin-gated, paginated lists, audit trail populated."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job

HOST = {"host": "spstechnosoft.com"}
PW = "AdminLocal!123"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="U", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def users():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    admin = _mk(db, sps, "admin6@local.test", ["owner"])
    rec = _mk(db, sps, "rec6@local.test", ["recruiter"])
    yield
    db.execute(delete(AuditLog).where(AuditLog.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    for u in (admin, rec):
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def test_non_admin_forbidden(users):
    c = TestClient(app); _login(c, "rec6@local.test")
    assert c.get("/api/admin/jobs", headers=HOST).status_code == 403


def test_admin_lists_and_audit_trail(users):
    rc = TestClient(app); _login(rc, "rec6@local.test")
    job = rc.post("/api/jobs", json={"title": "Admin-view Job"}, headers=HOST).json()
    cand = rc.post("/api/candidates", json={"full_name": "Asha Sharma"}, headers=HOST).json()
    appn = rc.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()
    rc.patch(f"/api/applications/{appn['id']}/stage", json={"stage": "screened"}, headers=HOST)

    ac = TestClient(app); _login(ac, "admin6@local.test")
    jobs = ac.get("/api/admin/jobs", headers=HOST).json()
    assert jobs["total"] >= 1 and {"items", "total", "limit", "offset"} <= jobs.keys()

    audit = ac.get("/api/admin/audit-logs", headers=HOST).json()
    actions = {row["action"] for row in audit["items"]}
    assert {"job.create", "application.create", "application.stage_change"} <= actions
