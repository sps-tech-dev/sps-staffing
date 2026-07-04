"""B.10 notification scaffolding: enqueue/render/idempotency, ConsoleChannel sweep,
unregistered-channel parking, consent gating (marketing only), retry/backoff, the
three wired stub sites, scoping."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app import notify
from app.config import settings
from app.db import get_sessionmaker
from app.jobs import dunning_sweep
from app.main import app
from app.models import (
    BusinessUnit, ClientUser, Consent, Membership, Notification, Tenant, User,
)
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Interview, InterviewSlot,
    Invoice, Job, Offer, Placement, Test,
)

HOST = {"host": "spstechnosoft.com"}
PW = "NotifyLocal!123"
RECRUITER = "ntf-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Ntf Tester", status="active")
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
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id))
    db.execute(delete(Test).where(Test.tenant_id == sps.id))
    db.execute(delete(InterviewSlot).where(InterviewSlot.tenant_id == sps.id))
    db.execute(delete(Invoice).where(Invoice.tenant_id == sps.id))
    db.execute(delete(Placement).where(Placement.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Interview, Offer, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _enq(db, sps, key, **over):
    kwargs = dict(template_code="assessment_result", recipient="cand@local.test",
                  vars={"candidate_name": "Asha", "job_title": "DevOps", "result": "pass"},
                  tenant_id=sps.id, idempotency_key=key)
    kwargs.update(over)
    row = notify.enqueue(db, **kwargs)
    db.commit()
    return row


def test_enqueue_renders_and_is_idempotent(env):
    sps, db = env
    key = f"t-{uuid.uuid4()}"
    row = _enq(db, sps, key)
    assert row.status == "pending" and row.channel_type == "console"   # dev override
    assert "Asha" in row.rendered_body and "DevOps" in row.rendered_body
    assert "pass" in row.rendered_body
    dup = _enq(db, sps, key, vars={"candidate_name": "SOMEONE ELSE"})
    assert dup.id == row.id                                            # no-op, same row
    n = db.execute(select(func.count()).select_from(Notification)
                   .where(Notification.idempotency_key == key)).scalar_one()
    assert n == 1


def test_console_sweep_sends_once(env):
    sps, db = env
    key = f"t-{uuid.uuid4()}"
    row = _enq(db, sps, key)
    r1 = notify.send_sweep(db)
    assert r1["sent"] >= 1
    db.refresh(row)
    assert row.status == "sent" and row.sent_at is not None and row.attempts == 1
    r2 = notify.send_sweep(db)                       # sent rows never re-send
    db.refresh(row)
    assert row.attempts == 1 and row.status == "sent"


def test_unregistered_channel_parks_pending(env, monkeypatch):
    sps, db = env
    monkeypatch.setattr(settings, "notify_channel_override", "")   # use template channel
    key = f"t-{uuid.uuid4()}"
    row = _enq(db, sps, key)
    assert row.channel_type == "email"               # the template's intended channel
    res = notify.send_sweep(db)
    db.refresh(row)
    assert row.status == "pending" and row.attempts == 0            # parked, untouched
    assert res["parked_unregistered"] >= 1


def test_marketing_requires_consent_txn_does_not(env):
    sps, db = env
    cand = Candidate(tenant_id=sps.id, full_name="Mkt Cand")
    db.add(cand); db.commit()
    # marketing WITHOUT consent → skipped
    row = _enq(db, sps, f"m-{uuid.uuid4()}", kind="marketing", subject_candidate_id=cand.id)
    assert row.status == "skipped" and row.last_error == "no marketing consent"
    # marketing WITH consent → pending
    db.add(Consent(tenant_id=sps.id, subject_candidate_id=cand.id, purpose="marketing",
                   granted=True, policy_version="p"))
    db.commit()
    row2 = _enq(db, sps, f"m-{uuid.uuid4()}", kind="marketing", subject_candidate_id=cand.id)
    assert row2.status == "pending"
    # transactional never consults marketing consent (no consent rows needed)
    row3 = _enq(db, sps, f"t-{uuid.uuid4()}")        # kind=txn default
    assert row3.status == "pending"


def test_retry_backoff_and_failed_cap(env, monkeypatch):
    sps, db = env

    class FlakyChannel(notify.AbstractChannel):
        channel_type = "console"
        def send(self, msg):
            return notify.DeliveryResult(ok=False, error="simulated outage")

    monkeypatch.setitem(notify.CHANNEL_REGISTRY, "console", FlakyChannel())
    monkeypatch.setattr(settings, "notify_max_attempts", 3)
    key = f"t-{uuid.uuid4()}"
    row = _enq(db, sps, key)
    for expected_attempts in (1, 2):
        notify.send_sweep(db); db.refresh(row)
        assert row.status == "pending" and row.attempts == expected_attempts
        assert row.last_error == "simulated outage"
    notify.send_sweep(db); db.refresh(row)
    assert row.status == "failed" and row.attempts == 3              # capped
    notify.send_sweep(db); db.refresh(row)
    assert row.attempts == 3                                          # failed never retried


def test_wired_site_assessment_result(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    job = c.post("/api/jobs", json={"title": "Ntf Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Ntf Cand", "phone": "9840100001",
                                           "email": "ntf-cand@local.test"}, headers=HOST).json()
    aid = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                 headers=HOST).json()["id"]
    v = 1
    for st in ("screening", "aptitude_test"):
        v = c.post(f"/api/applications/{aid}/transition",
                   json={"to_stage": st, "expected_version": v}, headers=HOST).json()["version"]
    issued = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST).json()
    token = issued["take_path"].rsplit("/", 1)[1]
    p = TestClient(app)
    p.get(f"/api/take/{token}")
    frozen = db.execute(select(Test).where(
        Test.id == uuid.UUID(issued["test_id"]))).scalar_one().served_questions
    answers = {f["qid"]: f["correct"] for f in frozen}
    assert p.post(f"/api/take/{token}/submit", json={"answers": answers}).status_code == 200
    p.post(f"/api/take/{token}/submit", json={"answers": answers})    # idempotent replay
    rows = db.execute(select(Notification).where(
        Notification.idempotency_key == f"assessment_result:{issued['test_id']}")).scalars().all()
    assert len(rows) == 1 and rows[0].status == "pending"
    assert "pass" in rows[0].rendered_body and rows[0].recipient == "ntf-cand@local.test"


def test_wired_site_interview_reminder(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    job = c.post("/api/jobs", json={"title": "Ntf IV Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Ntf IV Cand", "phone": "9840100002",
                                           "email": "ntf-iv@local.test"}, headers=HOST).json()
    aid = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                 headers=HOST).json()["id"]
    ivid = c.post(f"/api/applications/{aid}/interviews", json={"mode": "video"},
                  headers=HOST).json()["id"]
    base = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)
    slots = [{"start": (base + dt.timedelta(days=k)).isoformat(),
              "end": (base + dt.timedelta(days=k, hours=1)).isoformat()} for k in range(3)]
    r = c.post(f"/api/interviews/{ivid}/slots", json={"slots": slots}, headers=HOST).json()
    c.post(f"/api/interviews/{ivid}/slots/{r['slots'][0]['id']}/choose", headers=HOST)
    c.post(f"/api/interviews/{ivid}/slots/{r['slots'][0]['id']}/choose", headers=HOST)  # replay
    rows = db.execute(select(Notification).where(
        Notification.idempotency_key == f"interview_reminder:{ivid}:0")).scalars().all()
    assert len(rows) == 1 and "2026-09-01" in rows[0].rendered_body
    # reschedule → re-choose = NEW reminder under the bumped sequence key
    c.patch(f"/api/interviews/{ivid}", json={"status": "rescheduled"}, headers=HOST)
    r2 = c.post(f"/api/interviews/{ivid}/slots", json={"slots": slots}, headers=HOST).json()
    c.post(f"/api/interviews/{ivid}/slots/{r2['slots'][1]['id']}/choose", headers=HOST)
    n = db.execute(select(func.count()).select_from(Notification).where(
        Notification.template_code == "interview_reminder")).scalar_one()
    assert n == 2


def test_wired_site_dunning(env):
    sps, db = env
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Ntf DunCo")
    db.add(client); db.flush()
    cu_user = User(tenant_id=sps.id, email="ntf-clientadmin@local.test",
                   password_hash=PasswordHasher().hash(PW), full_name="CA", status="active")
    db.add(cu_user); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=cu_user.id, client_id=client.id,
                      status="active"))
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Dun Job", client_id=client.id)
    cand = Candidate(tenant_id=sps.id, full_name="Dun Cand")
    db.add_all([job, cand]); db.flush()
    appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, client_id=client.id, stage="joined")
    db.add(appn); db.flush()
    inv = Invoice(tenant_id=sps.id, business_unit_id="STAFFING", application_id=appn.id,
                  client_id=client.id, base_amount=1_000_000, fee_percent=15,
                  fee_amount=150000, total_amount=150000, status="issued")
    db.add(inv); db.commit()
    inv.created_at = inv.created_at - dt.timedelta(days=45)
    db.commit()
    dunning_sweep(db, enqueue_sends=True)
    dunning_sweep(db, enqueue_sends=True)             # idempotent: one notice per invoice
    rows = db.execute(select(Notification).where(
        Notification.idempotency_key == f"invoice_dunning:{inv.id}")).scalars().all()
    assert len(rows) == 1
    assert rows[0].recipient == "ntf-clientadmin@local.test"
    assert "45" in rows[0].rendered_body and "PROV-" in rows[0].rendered_body
    db.execute(delete(ClientUser).where(ClientUser.user_id == cu_user.id))
    db.execute(delete(User).where(User.id == cu_user.id)); db.commit()


def test_read_endpoint_scoped_and_gated(env):
    sps, db = env
    _enq(db, sps, f"t-{uuid.uuid4()}")
    assert TestClient(app).get("/api/notifications", headers=HOST).status_code == 401
    c = TestClient(app); _login(c, RECRUITER)
    rows = c.get("/api/notifications", headers=HOST).json()
    assert rows and rows[0]["channel_type"] == "console"
    # tenant B sees nothing
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB12")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB12", slug="testb12", name="Tenant B12"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "ntf-b@local.test", ["recruiter"])
    try:
        cb = TestClient(app); _login(cb, "ntf-b@local.test", {"host": "testb12.spstechnosoft.com"})
        assert cb.get("/api/notifications", headers={"host": "testb12.spstechnosoft.com"}).json() == []
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
