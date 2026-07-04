"""B.13 vendor depth: dynamic commission resolution (4 levels), rate lock at
placement date, no-double-count (replacement + credit-note auto-void), scorecard."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Invoice, Job, Offer, Placement,
    Vendor, VendorClientRate, VendorCommission, VendorContract, VendorSubmission,
)

HOST = {"host": "spstechnosoft.com"}
PW = "VendLocal!123"
RECRUITER = "vd-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Vd Tester", status="active")
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
    yield sps, db
    for M in (VendorCommission, VendorClientRate, VendorContract, VendorSubmission,
              Vendor, Invoice, Placement, CandidateTimeline):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    for M in (Offer, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _world(db, sps, c, tag, joined=None, ctc=1_000_000):
    """vendor + client + job + candidate + vendor_submission + joined app +
    placement-with-invoice (via the B.9 endpoint). Returns dict of objects."""
    joined = joined or dt.date(2026, 7, 1)
    vendor = Vendor(tenant_id=sps.id, business_unit_id="STAFFING", name=f"Vend {tag}")
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name=f"VdClient {tag}")
    db.add_all([vendor, client]); db.flush()
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title=f"Vd Job {tag}",
              client_id=client.id)
    cand = Candidate(tenant_id=sps.id, full_name=f"Vd Cand {tag}")
    db.add_all([job, cand]); db.flush()
    db.add(VendorSubmission(tenant_id=sps.id, business_unit_id="STAFFING",
                            vendor_id=vendor.id, candidate_id=cand.id, job_id=job.id))
    appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, client_id=client.id, stage="joined")
    db.add(appn); db.flush()
    db.add(Offer(tenant_id=sps.id, business_unit_id="STAFFING", application_id=appn.id,
                 client_id=client.id, ctc=ctc, joining_date=joined, status="accepted"))
    db.commit()
    plc = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST).json()
    return {"vendor": vendor, "client": client, "job": job, "cand": cand,
            "app": appn, "plc": plc}


def _contract(c, vendor_id, pct, valid_from="2026-01-01", valid_until=None):
    r = c.post(f"/api/vendors/{vendor_id}/contracts",
               json={"base_commission_percent": pct, "valid_from": valid_from,
                     "valid_until": valid_until}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()


def _accrue(c, placement_id, **body):
    return c.post(f"/api/placements/{placement_id}/commission", json=body, headers=HOST)


def test_resolution_levels(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    # level 3: contract base
    w = _world(db, sps, c, "L3")
    _contract(c, str(w["vendor"].id), 8)
    r = _accrue(c, w["plc"]["id"]).json()
    assert r["resolved_percent"] == 8.0 and r["source_level"] == "contract_base"
    assert r["base_amount"] == 150000.0 and r["commission_amount"] == 12000.0  # fee×8%
    # level 2: client rate beats contract
    w2 = _world(db, sps, c, "L2")
    _contract(c, str(w2["vendor"].id), 8)
    c.put(f"/api/vendors/{w2['vendor'].id}/client-rates",
          json={"client_id": str(w2["client"].id), "commission_percent": 12}, headers=HOST)
    r2 = _accrue(c, w2["plc"]["id"]).json()
    assert r2["resolved_percent"] == 12.0 and r2["source_level"] == "client_rate"
    # level 1: placement override beats client rate
    w3 = _world(db, sps, c, "L1")
    _contract(c, str(w3["vendor"].id), 8)
    c.put(f"/api/vendors/{w3['vendor'].id}/client-rates",
          json={"client_id": str(w3["client"].id), "commission_percent": 12}, headers=HOST)
    r3 = _accrue(c, w3["plc"]["id"], override_percent=5).json()
    assert r3["resolved_percent"] == 5.0 and r3["source_level"] == "placement_override"
    # level 4 absent (config None): nothing resolves → 409, no invented rate
    w4 = _world(db, sps, c, "L4")
    r4 = _accrue(c, w4["plc"]["id"])
    assert r4.status_code == 409 and r4.json()["error"]["code"] == "NO_COMMISSION_BASIS"


def test_client_dynamic_same_vendor_two_clients(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "CD1")
    vendor = w["vendor"]
    _contract(c, str(vendor.id), 8)
    # second client + placement sourced by the SAME vendor
    client2 = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="VdClient CD2")
    db.add(client2); db.flush()
    job2 = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Vd Job CD2",
               client_id=client2.id)
    cand2 = Candidate(tenant_id=sps.id, full_name="Vd Cand CD2")
    db.add_all([job2, cand2]); db.flush()
    db.add(VendorSubmission(tenant_id=sps.id, business_unit_id="STAFFING",
                            vendor_id=vendor.id, candidate_id=cand2.id, job_id=job2.id))
    app2 = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job2.id,
                       candidate_id=cand2.id, client_id=client2.id, stage="joined")
    db.add(app2); db.flush()
    db.add(Offer(tenant_id=sps.id, business_unit_id="STAFFING", application_id=app2.id,
                 client_id=client2.id, ctc=1_000_000, joining_date=dt.date(2026, 7, 1),
                 status="accepted"))
    db.commit()
    plc2 = c.post(f"/api/applications/{app2.id}/placement", json={}, headers=HOST).json()
    # client 1 → 10%, client 2 → 15% for the SAME vendor
    c.put(f"/api/vendors/{vendor.id}/client-rates",
          json={"client_id": str(w["client"].id), "commission_percent": 10}, headers=HOST)
    c.put(f"/api/vendors/{vendor.id}/client-rates",
          json={"client_id": str(client2.id), "commission_percent": 15}, headers=HOST)
    r1 = _accrue(c, w["plc"]["id"]).json()
    r2 = _accrue(c, plc2["id"]).json()
    assert r1["resolved_percent"] == 10.0 and r2["resolved_percent"] == 15.0, \
        "client-dynamic rate is not actually per-client"


def test_rate_lock_no_retro_alter(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "LOCK")
    _contract(c, str(w["vendor"].id), 8)
    r = _accrue(c, w["plc"]["id"]).json()
    assert r["resolved_percent"] == 8.0
    # rate changes AFTER accrual must not retro-alter the materialized row
    c.put(f"/api/vendors/{w['vendor'].id}/client-rates",
          json={"client_id": str(w["client"].id), "commission_percent": 20}, headers=HOST)
    rows = c.get(f"/api/vendors/{w['vendor'].id}/commissions", headers=HOST).json()
    assert rows[0]["resolved_percent"] == 8.0 and rows[0]["commission_amount"] == 12000.0
    # contract valid-at-placement-date: a contract starting AFTER joined_on doesn't apply
    w2 = _world(db, sps, c, "LATE")
    _contract(c, str(w2["vendor"].id), 9, valid_from="2026-08-01")   # joined 2026-07-01
    r2 = _accrue(c, w2["plc"]["id"])
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "NO_COMMISSION_BASIS"


def test_no_double_count(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "NDC")
    _contract(c, str(w["vendor"].id), 8)
    # duplicate accrual blocked
    _accrue(c, w["plc"]["id"])
    dup = _accrue(c, w["plc"]["id"])
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "COMMISSION_EXISTS"
    # credit-noting the fee AUTO-VOIDS the accrued commission
    cn = c.post(f"/api/invoices/{w['plc']['invoice_id']}/credit-note", headers=HOST)
    assert cn.status_code == 200
    rows = c.get(f"/api/vendors/{w['vendor'].id}/commissions", headers=HOST).json()
    assert rows[0]["status"] == "void" and "credit-noted" in rows[0]["void_reason"]
    # replacement placements accrue nothing
    b = c.post(f"/api/placements/{w['plc']['id']}/breach",
               json={"reason": "left"}, headers=HOST)
    assert b.status_code == 200
    cand3 = Candidate(tenant_id=sps.id, full_name="Vd Repl NDC")
    db.add(cand3); db.flush()
    app3 = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=w["job"].id,
                       candidate_id=cand3.id, client_id=w["client"].id, stage="joined")
    db.add(app3); db.commit()
    rep = c.post(f"/api/placements/{w['plc']['id']}/replacement",
                 json={"application_id": str(app3.id)}, headers=HOST).json()
    r = _accrue(c, rep["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "REPLACEMENT_NO_FEE"


def test_no_sourcing_trail_refused(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "TRAIL")
    _contract(c, str(w["vendor"].id), 8)
    db.execute(delete(VendorSubmission).where(VendorSubmission.tenant_id == sps.id))
    db.commit()
    r = _accrue(c, w["plc"]["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_SOURCING_TRAIL"


def test_scorecard_and_lifecycle(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "SCORE")
    _contract(c, str(w["vendor"].id), 10)
    acc = _accrue(c, w["plc"]["id"]).json()
    sc = c.get(f"/api/vendors/{w['vendor'].id}/scorecard", headers=HOST).json()
    assert sc["submissions"] == 1 and sc["placements"] == 1
    assert sc["conversion_rate"] == 1.0
    assert sc["commission_accrued"] == 15000.0 and sc["commission_paid"] == 0
    assert sc["avg_time_to_fill_days"] is not None
    # lifecycle: paid; void-after-paid refused
    assert c.post(f"/api/vendors/commissions/{acc['id']}/mark-paid",
                  headers=HOST).json()["status"] == "paid"
    v = c.post(f"/api/vendors/commissions/{acc['id']}/void",
               json={"reason": "nope"}, headers=HOST)
    assert v.status_code == 409 and v.json()["error"]["code"] == "ALREADY_PAID"
    sc2 = c.get(f"/api/vendors/{w['vendor'].id}/scorecard", headers=HOST).json()
    assert sc2["commission_paid"] == 15000.0 and sc2["commission_accrued"] == 0


def test_gates(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    w = _world(db, sps, c, "GATE")
    assert TestClient(app).get(f"/api/vendors/{w['vendor'].id}/scorecard",
                               headers=HOST).status_code == 401
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB15")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB15", slug="testb15", name="Tenant B15"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "vd-b@local.test", ["recruiter"])
    try:
        cb = TestClient(app); _login(cb, "vd-b@local.test", {"host": "testb15.spstechnosoft.com"})
        assert cb.get(f"/api/vendors/{w['vendor'].id}/scorecard",
                      headers={"host": "testb15.spstechnosoft.com"}).status_code == 404
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
