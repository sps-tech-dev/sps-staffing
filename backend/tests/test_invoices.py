"""Invoices: 15% placement fee + configurable (never hardcoded) GST/TDS, status."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Client, Invoice, Job

HOST = {"host": "spstechnosoft.com"}
PW = "InvLocal!123"
EMAIL = "inv@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Inv", status="active"); db.add(u); db.flush()
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
    db.execute(delete(Invoice).where(Invoice.tenant_id == sps.id))
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c, email=EMAIL):
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200


def _seed_app(c):
    client = c.post("/api/clients", json={"name": "Acme Corp"}, headers=HOST).json()
    job = c.post("/api/jobs", json={"title": "Director", "client_id": client["id"]}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Vivek Nair"}, headers=HOST).json()
    return c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]}, headers=HOST).json()["id"]


def test_invoice_15pct_fee_no_tax_until_supplied(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    inv = c.post("/api/invoices", json={"application_id": app_id, "base_amount": 1000000}, headers=HOST)
    assert inv.status_code == 200, inv.text
    b = inv.json()
    # 15% default fee; NO GST/TDS applied (rates not supplied → None) → total == fee
    assert b["fee_percent"] == 15.0 and b["fee_amount"] == 150000.0
    assert b["gst_percent"] is None and b["gst_amount"] is None
    assert b["tds_percent"] is None and b["tds_amount"] is None
    assert b["total_amount"] == 150000.0 and b["currency"] == "INR" and b["status"] == "draft"
    iid = b["id"]

    # supply GST 18% + TDS 10% (configurable) → recompute
    upd = c.patch(f"/api/invoices/{iid}", json={"gst_percent": 18, "tds_percent": 10, "status": "issued"}, headers=HOST).json()
    assert upd["gst_amount"] == 27000.0 and upd["tds_amount"] == 15000.0
    assert upd["total_amount"] == 162000.0 and upd["status"] == "issued"  # 150000 + 27000 - 15000

    row = next(i for i in c.get("/api/invoices", headers=HOST).json() if i["id"] == iid)
    assert row["candidate"] == "Vivek Nair" and row["job"] == "Director"


def test_invoice_custom_fee_percent(recruiter):
    c = TestClient(app); _login(c)
    app_id = _seed_app(c)
    b = c.post("/api/invoices", json={"application_id": app_id, "base_amount": 2000000, "fee_percent": 12.5}, headers=HOST).json()
    assert b["fee_percent"] == 12.5 and b["fee_amount"] == 250000.0


def test_invoice_requires_staff_role():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, "inv-cand@local.test", ["candidate"])
    try:
        import uuid
        c = TestClient(app); _login(c, "inv-cand@local.test")
        assert c.post("/api/invoices", json={"application_id": str(uuid.uuid4()), "base_amount": 1}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
