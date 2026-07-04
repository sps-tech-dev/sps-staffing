"""B.9 commercial layer: annual-CTC fee base, fee resolution (invoice→client→15),
guarantee derivability + idempotent sweep, breach/reopen, replacement no-double-fee,
commission attribution, invoice PDF (S3), overdue detection, scoping."""
from __future__ import annotations

import datetime as dt
import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, func, select

from app.config import settings
from app.db import get_sessionmaker
from app.jobs import derived_guarantee_state, dunning_sweep, guarantee_sweep
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Interview, Invoice, Job, Offer,
    Placement, Submission,
)

HOST = {"host": "spstechnosoft.com"}
PW = "PlaceLocal!123"
RECRUITER = "plc-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Plc Tester", status="active")
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
    db.execute(delete(Invoice).where(Invoice.tenant_id == sps.id))
    db.execute(delete(Placement).where(Placement.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Interview, Submission, Offer, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _joined_app(db, sps, c, phone, client_fee=None, ctc=1_200_000):
    """Build a joined application directly (stage vocabulary lives in pipeline;
    here we need the END state to exercise the commercial layer)."""
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name=f"PlcCo {phone}",
                    **({"fee_percent": client_fee} if client_fee is not None else {}))
    db.add(client); db.flush()
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title=f"Plc Job {phone}",
              client_id=client.id)
    cand = Candidate(tenant_id=sps.id, full_name=f"Plc Cand {phone}")
    db.add_all([job, cand]); db.flush()
    rec_user = db.execute(select(User).where(User.email == RECRUITER)).scalar_one()
    appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, client_id=client.id, stage="joined",
                       owner_id=rec_user.id)
    db.add(appn); db.flush()
    offer = Offer(tenant_id=sps.id, business_unit_id="STAFFING", application_id=appn.id,
                  client_id=client.id, ctc=ctc, joining_date=dt.date(2026, 7, 1),
                  status="accepted")
    db.add(offer); db.commit()
    return client, job, cand, appn


def test_annual_ctc_fee_base_and_default_15(env):
    """THE fee test: 12,00,000 annual CTC × 15% = 1,80,000. A monthly
    misinterpretation would produce 15,000 × 12 discrepancy — caught here."""
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _client, _job, cand, appn = _joined_app(db, sps, c, "01", ctc=1_200_000)
    r = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fee_percent"] == 15.0
    assert body["fee_amount"] == 180000.0          # 1,200,000 × 15% — ANNUAL base
    assert body["total_amount"] == 180000.0        # GST/TDS inert → total == fee
    assert body["guarantee_until"] == "2026-08-30"  # joined 2026-07-01 + 60d
    assert body["recruiter_id"] is not None        # attribution from application owner
    tl = c.get(f"/api/candidates/{cand.id}/timeline", headers=HOST,
               params={"event_type": "Joining"}).json()
    assert len(tl) == 1 and tl[0]["payload"]["placement_id"] == body["id"]


def test_fee_resolution_order(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    # client rate 12% beats global 15
    _cl, _j, _cd, app1 = _joined_app(db, sps, c, "02", client_fee=12, ctc=1_000_000)
    r1 = c.post(f"/api/applications/{app1.id}/placement", json={}, headers=HOST).json()
    assert r1["fee_percent"] == 12.0 and r1["fee_amount"] == 120000.0
    # invoice override 10% beats client rate 12
    _cl, _j, _cd, app2 = _joined_app(db, sps, c, "03", client_fee=12, ctc=1_000_000)
    r2 = c.post(f"/api/applications/{app2.id}/placement",
                json={"fee_percent": 10}, headers=HOST).json()
    assert r2["fee_percent"] == 10.0 and r2["fee_amount"] == 100000.0


def test_guarantee_derivable_without_job_run(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, _cd, appn = _joined_app(db, sps, c, "04")
    c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    p = db.execute(select(Placement).where(Placement.application_id == appn.id)).scalar_one()
    # within the window → in_guarantee; after → cleared — WITHOUT any sweep run
    assert derived_guarantee_state(p, today=dt.date(2026, 7, 15)) == "in_guarantee"
    assert derived_guarantee_state(p, today=dt.date(2026, 9, 15)) == "cleared"
    assert p.status == "active"                     # materialized state untouched
    listed = c.get("/api/placements", headers=HOST).json()
    assert listed[0]["derived_state"] in ("in_guarantee", "cleared")


def test_guarantee_sweep_idempotent(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, cand, appn = _joined_app(db, sps, c, "05")
    c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    p = db.execute(select(Placement).where(Placement.application_id == appn.id)).scalar_one()
    p.joined_on = dt.date(2025, 10, 1)              # back-date coherently (CHECK:
    p.guarantee_until = dt.date(2025, 11, 30)       # guarantee_until >= joined_on)
    db.commit()
    assert guarantee_sweep(db) == 1                 # first run materializes
    assert guarantee_sweep(db) == 0                 # second run: no-op (self-heal safe)
    db.refresh(p)
    assert p.status == "cleared"
    n = db.execute(select(func.count()).select_from(CandidateTimeline).where(
        CandidateTimeline.candidate_id == cand.id,
        CandidateTimeline.event_type == "GuaranteeCompletion")).scalar_one()
    assert n == 1, "sweep double-emitted"


def test_breach_requires_reason_reopens_job(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, job, cand, appn = _joined_app(db, sps, c, "06")
    plc = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST).json()
    job_row = db.get(Job, job.id)
    job_row.status = "filled"
    db.commit()
    r = c.post(f"/api/placements/{plc['id']}/breach", json={"reason": ""}, headers=HOST)
    assert r.status_code == 422
    r = c.post(f"/api/placements/{plc['id']}/breach",
               json={"reason": "candidate resigned day 20"}, headers=HOST)
    assert r.status_code == 200 and r.json()["status"] == "breached"
    db.refresh(job_row)
    assert job_row.status == "open"                 # requisition reopened (existing flag)
    tl = c.get(f"/api/candidates/{cand.id}/timeline", headers=HOST,
               params={"event_type": "GuaranteeCompletion"}).json()
    assert tl and tl[-1]["payload"]["outcome"] == "breached"


def test_replacement_no_double_fee(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    client, job, _cd, appn = _joined_app(db, sps, c, "07", ctc=1_000_000)
    plc = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST).json()
    c.post(f"/api/placements/{plc['id']}/breach", json={"reason": "left"}, headers=HOST)
    # replacement candidate on the SAME job, already joined
    cand2 = Candidate(tenant_id=sps.id, full_name="Plc Replacement")
    db.add(cand2); db.flush()
    app2 = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand2.id, client_id=client.id, stage="joined")
    db.add(app2); db.commit()
    r = c.post(f"/api/placements/{plc['id']}/replacement",
               json={"application_id": str(app2.id)}, headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fee_exempt"] is True and body["replacement_for"] == plc["id"]
    # original flipped to replaced; NO second invoice exists (revenue not double-counted)
    orig = db.get(Placement, uuid.UUID(plc["id"])); db.refresh(orig)
    assert orig.status == "replaced"
    n_inv = db.execute(select(func.count()).select_from(Invoice).where(
        Invoice.tenant_id == sps.id, Invoice.credit_note_of.is_(None))).scalar_one()
    assert n_inv == 1, "replacement raised a second fee invoice!"
    # credit-note structure against the original invoice
    inv_id = plc["invoice_id"]
    cn = c.post(f"/api/invoices/{inv_id}/credit-note", headers=HOST)
    assert cn.status_code == 200 and cn.json()["total_amount"] == -150000.0
    assert c.post(f"/api/invoices/{inv_id}/credit-note", headers=HOST).status_code == 409


def test_commission_attribution(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, _cd, appn = _joined_app(db, sps, c, "08", ctc=2_000_000)
    c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    rows = c.get("/api/placements/commissions", headers=HOST).json()
    rec_user = db.execute(select(User).where(User.email == RECRUITER)).scalar_one()
    mine = next(r for r in rows if r["recruiter_id"] == str(rec_user.id))
    assert mine["placements"] == 1 and mine["billed_fees"] == 300000.0   # 2M × 15%


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.storage_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region})
        yield boto3.client("s3", region_name=settings.aws_region)


def test_invoice_pdf_renders_with_pending_tax_lines(env, s3):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, _cd, appn = _joined_app(db, sps, c, "09")
    plc = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST).json()
    r = c.get(f"/api/invoices/{plc['invoice_id']}/pdf", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["number"].startswith("PROV-") and body["download_url"].startswith("http")
    obj = s3.get_object(Bucket=settings.storage_bucket, Key=body["s3_key"])["Body"].read()
    assert obj.startswith(b"%PDF"), "not a valid PDF"
    # content honesty: fee line + pending GST/TDS lines, provisional numbering marker
    from pdfminer.high_level import extract_text
    import io
    text = extract_text(io.BytesIO(obj))
    assert "Placement service fee (15% of annual CTC)" in text
    assert "GST" in text and "pending" in text and "TDS" in text
    assert "PROVISIONAL" in text
    assert "pre-tax" in text                       # total is never presented as taxed


def test_overdue_detection_and_stubbed_send(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, _cd, appn = _joined_app(db, sps, c, "10")
    plc = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST).json()
    inv = db.get(Invoice, uuid.UUID(plc["invoice_id"]))
    assert dunning_sweep(db) == []                 # fresh invoice: not overdue
    inv.created_at = inv.created_at - dt.timedelta(days=45)
    db.commit()
    hits = c.get("/api/invoices/overdue", headers=HOST).json()
    assert len(hits) == 1 and hits[0]["invoice_id"] == plc["invoice_id"]
    assert hits[0]["age_days"] >= 45


def test_gates_and_preconditions(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cl, _j, _cd, appn = _joined_app(db, sps, c, "11")
    # wrong stage → 409
    a2 = db.get(Application, appn.id)
    a2.stage = "offer_accepted"; db.commit()
    r = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "STAGE_INVALID"
    a2.stage = "joined"; db.commit()
    ok = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    assert ok.status_code == 200
    # duplicate placement → 409
    dup = c.post(f"/api/applications/{appn.id}/placement", json={}, headers=HOST)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "PLACEMENT_EXISTS"
    # unauth → 401
    assert TestClient(app).get("/api/placements", headers=HOST).status_code == 401
    # tenant B sees nothing
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB11")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB11", slug="testb11", name="Tenant B11"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "plc-b@local.test", ["recruiter"])
    try:
        cb = TestClient(app); _login(cb, "plc-b@local.test", {"host": "testb11.spstechnosoft.com"})
        assert cb.get("/api/placements", headers={"host": "testb11.spstechnosoft.com"}).json() == []
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
