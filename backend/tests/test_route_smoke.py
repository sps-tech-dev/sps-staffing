"""B.5-fix: regression tests for the two endpoints that 500'd since B.5, plus the
ROUTE-SMOKE MATRIX — the permanent class-guard: every GET /api route must return
non-500 under a valid session. This is the net that would have caught the deleted-
TRANSITIONS readers on the day B.5 landed."""
from __future__ import annotations

import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import Activity, BusinessUnit, ClientUser, Consent, Lead, Membership, Notification, Tenant, User
from app.models_staffing import (
    APPLICATION_STAGES, Application, Candidate, CandidateTimeline, Client, Interview,
    Invoice, Job, Offer, Placement, Submission, Vendor, VendorSubmission,
)

HOST = {"host": "spstechnosoft.com"}
PW = "SmokeLocal!123"
RECRUITER = "smoke-rec@local.test"
OWNER = "smoke-owner@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Smoke Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def world(monkeypatch):
    """One seeded row of every major entity, so GET routes with path params hit
    real objects (unknown params fall back to random uuids → 404s, which pass)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.storage_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region})
        db = get_sessionmaker()()
        sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
        rec = _mk_user(db, sps, RECRUITER, ["recruiter"])
        own = _mk_user(db, sps, OWNER, ["owner"])
        client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Smoke Co")
        db.add(client); db.flush()
        job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Smoke Job",
                  client_id=client.id)
        cand = Candidate(tenant_id=sps.id, full_name="Smoke Cand")
        vendor = Vendor(tenant_id=sps.id, business_unit_id="STAFFING", name="Smoke Vendor")
        lead = Lead(tenant_id=sps.id, business_unit_id="STAFFING", company="Smoke Lead Co")
        db.add_all([job, cand, vendor, lead]); db.flush()
        appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, client_id=client.id, stage="screening")
        db.add(appn); db.flush()
        iv = Interview(tenant_id=sps.id, business_unit_id="STAFFING",
                       application_id=appn.id, mode="video")
        import datetime as dt
        db.add(iv)
        # placement needs its own application (unique job+candidate) — second candidate
        cand2 = Candidate(tenant_id=sps.id, full_name="Smoke Cand Two")
        db.add(cand2); db.flush()
        app2 = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand2.id, client_id=client.id, stage="joined")
        db.add(app2); db.flush()
        plc = Placement(tenant_id=sps.id, business_unit_id="STAFFING", application_id=app2.id,
                        client_id=client.id, candidate_id=cand2.id, offered_ctc=1_000_000,
                        joined_on=dt.date(2026, 7, 1), guarantee_until=dt.date(2026, 8, 30))
        db.add(plc); db.flush()
        inv = Invoice(tenant_id=sps.id, business_unit_id="STAFFING", application_id=app2.id,
                      client_id=client.id, placement_id=plc.id, base_amount=1_000_000,
                      fee_percent=15, fee_amount=150000, total_amount=150000, status="draft")
        db.add(inv); db.commit()
        ids = {"candidate_id": str(cand.id), "job_id": str(job.id), "app_id": str(appn.id),
               "application_id": str(appn.id), "interview_id": str(iv.id),
               "invoice_id": str(inv.id), "placement_id": str(plc.id),
               "vendor_id": str(vendor.id), "lead_id": str(lead.id),
               "review_id": "999999", "token": "smoke-token-not-real"}
        yield sps, db, ids
        db.execute(delete(Notification).where(Notification.tenant_id == sps.id))
        db.execute(delete(Activity).where(Activity.tenant_id == sps.id))
        db.execute(delete(Lead).where(Lead.tenant_id == sps.id))
        db.execute(delete(Invoice).where(Invoice.tenant_id == sps.id))
        db.execute(delete(Placement).where(Placement.tenant_id == sps.id))
        db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
        db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
        for M in (VendorSubmission, Vendor, Interview, Submission, Offer, Application,
                  Job, Candidate, Client):
            db.execute(delete(M).where(M.tenant_id == sps.id))
        for u in (rec, own):
            db.execute(delete(Membership).where(Membership.user_id == u.id))
            db.execute(delete(User).where(User.id == u.id))
        db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


# ── regression 1: the kanban source (500 since B.5) ─────────────
def test_job_pipeline_200_with_full_new_vocabulary(world):
    sps, db, ids = world
    c = TestClient(app); _login(c, RECRUITER)
    r = c.get(f"/api/jobs/{ids['job_id']}/pipeline", headers=HOST)
    assert r.status_code == 200, r.text
    stages = r.json()["stages"]
    assert set(stages.keys()) == set(APPLICATION_STAGES)     # every B.5 bucket present
    assert any(row["id"] == ids["app_id"] for row in stages["screening"])
    assert len(stages["joined"]) == 1                        # the placement's app bucketed


# ── regression 2: the employer overview (500 + dead vocabulary since B.5) ──
def test_employer_overview_correct_nonzero_counts(world):
    sps, db, ids = world
    c = TestClient(app); _login(c, RECRUITER)
    r = c.get("/api/client-portal/overview", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    # seeded: 1 screening + 1 joined → NON-ZERO proof (a name-only fix would zero these)
    assert body["inPipeline"] == 1                           # screening only
    assert body["placements"] == 1                           # the joined placement app
    funnel = {f["label"]: f["value"] for f in body["funnel"]}
    assert funnel["Screening"] == 1 and funnel["Joined"] == 1
    assert body["openJobs"] == 1
    # the funnel speaks the NEW grouped vocabulary
    assert set(funnel.keys()) == {"Screening", "Assessment", "Internal", "Submitted",
                                  "Client Rounds", "Offer", "Joined"}


# ── the class-guard: no shipped GET route may 500 under a valid session ──
def _get_routes():
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute) and "GET" in r.methods and r.path.startswith("/api"):
            out.append(r.path)
    return sorted(out)


def test_route_smoke_matrix_no_get_500s(world):
    sps, db, ids = world
    rec = TestClient(app); _login(rec, RECRUITER)
    own = TestClient(app); _login(own, OWNER)
    failures = []
    for path in _get_routes():
        filled = path
        for name in ("candidate_id", "job_id", "app_id", "application_id", "interview_id",
                     "invoice_id", "placement_id", "vendor_id", "lead_id", "review_id",
                     "token"):
            filled = filled.replace("{" + name + "}", ids.get(name, str(uuid.uuid4())))
        # any leftover unknown params → random uuid (404s are acceptable; 500s are not)
        import re as _re
        filled = _re.sub(r"\{[^}]+\}", str(uuid.uuid4()), filled)
        for session_name, client in (("recruiter", rec), ("owner", own)):
            resp = client.get(filled, headers=HOST)
            if resp.status_code >= 500:
                failures.append(f"{path} [{session_name}] → {resp.status_code}")
    assert not failures, "GET routes returned 5xx under a valid session:\n" + "\n".join(failures)

# ── F2a: pipeline rows carry `version` (the optimistic-lock enabler) ──
def test_pipeline_rows_expose_version(world):
    sps, db, ids = world
    c = TestClient(app); _login(c, RECRUITER)
    stages = c.get(f"/api/jobs/{ids['job_id']}/pipeline", headers=HOST).json()["stages"]
    row = next(r for r in stages["screening"] if r["id"] == ids["app_id"])
    assert isinstance(row["version"], int) and row["version"] >= 1
