"""Offers: creation (CTC, joining date), RTR + acceptance tracking, staff-gate."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Job, Offer

HOST = {"host": "spstechnosoft.com"}
PW = "OfferLocal!123"
EMAIL = "offer@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Off", status="active"); db.add(u); db.flush()
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
    db.execute(delete(Offer).where(Offer.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def _seed_app(c):
    job = c.post("/api/jobs", json={"title": "SRE"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Ravi Kumar"}, headers=HOST).json()
    return c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()["id"]


def test_offer_create_rtr_and_acceptance(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    off = c.post(f"/api/applications/{app_id}/offers", json={"ctc": 1800000, "joining_date": "2026-08-01"}, headers=HOST)
    assert off.status_code == 200, off.text
    oid = off.json()["id"]
    assert off.json()["status"] == "draft" and off.json()["ctc"] == 1800000.0
    assert off.json()["joining_date"] == "2026-08-01"

    # release → RTR signed → accepted
    assert c.patch(f"/api/offers/{oid}", json={"status": "released"}, headers=HOST).json()["status"] == "released"
    rtr = c.patch(f"/api/offers/{oid}", json={"rtr_signed": True}, headers=HOST).json()
    assert rtr["rtr_signed_at"] is not None
    acc = c.patch(f"/api/offers/{oid}", json={"status": "accepted"}, headers=HOST).json()
    assert acc["status"] == "accepted" and acc["accepted_at"] is not None

    # dashboard
    row = next(o for o in c.get("/api/offers", headers=HOST).json() if o["id"] == oid)
    assert row["candidate"] == "Ravi Kumar" and row["job"] == "SRE"


def test_offer_bad_status_422(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    oid = c.post(f"/api/applications/{app_id}/offers", json={}, headers=HOST).json()["id"]
    assert c.patch(f"/api/offers/{oid}", json={"status": "nope"}, headers=HOST).status_code == 422


def test_offer_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "offer-cand@local.test", ["candidate"])
    try:
        import uuid
        c = TestClient(app); _login(c, "offer-cand@local.test")
        assert c.post(f"/api/applications/{uuid.uuid4()}/offers", json={}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
