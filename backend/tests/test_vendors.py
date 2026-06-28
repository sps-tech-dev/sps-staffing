"""Vendors + vendor submissions: create/list/update, attribution, staff-gate."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Candidate, Vendor, VendorSubmission

HOST = {"host": "spstechnosoft.com"}
PW = "VendLocal!123"
EMAIL = "vend@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Vend", status="active"); db.add(u); db.flush()
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
    db.execute(delete(VendorSubmission).where(VendorSubmission.tenant_id == sps.id))
    db.execute(delete(Vendor).where(Vendor.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def test_vendor_and_submission_flow(recruiter):
    c = TestClient(app); _login(c)
    ven = c.post("/api/vendors", json={"name": "Partner Agency", "contact_email": "ops@partner.com", "commission_percent": 8}, headers=HOST)
    assert ven.status_code == 200, ven.text
    vid = ven.json()["id"]
    assert ven.json()["status"] == "active" and ven.json()["commission_percent"] == 8.0

    upd = c.patch(f"/api/vendors/{vid}", json={"status": "inactive", "commission_percent": 10}, headers=HOST).json()
    assert upd["status"] == "inactive" and upd["commission_percent"] == 10.0
    assert any(v["id"] == vid for v in c.get("/api/vendors", headers=HOST).json())

    # vendor submits a candidate (attribution)
    cand = c.post("/api/candidates", json={"full_name": "Sunil Verma"}, headers=HOST).json()
    sub = c.post(f"/api/vendors/{vid}/submissions", json={"candidate_id": cand["id"], "notes": "from job board"}, headers=HOST)
    assert sub.status_code == 200, sub.text
    sid = sub.json()["id"]
    assert c.patch(f"/api/vendor-submissions/{sid}", json={"status": "shortlisted"}, headers=HOST).json()["status"] == "shortlisted"

    row = next(s for s in c.get("/api/vendor-submissions", headers=HOST).json() if s["id"] == sid)
    assert row["vendor"] == "Partner Agency" and row["candidate"] == "Sunil Verma"


def test_vendor_bad_status_422(recruiter):
    c = TestClient(app); _login(c)
    vid = c.post("/api/vendors", json={"name": "X Co"}, headers=HOST).json()["id"]
    assert c.patch(f"/api/vendors/{vid}", json={"status": "paused"}, headers=HOST).status_code == 422


def test_vendor_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "vend-cand@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "vend-cand@local.test")
        assert c.post("/api/vendors", json={"name": "Y"}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
