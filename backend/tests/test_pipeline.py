"""B.5 pipeline state machine: transition matrix, RTR gate, reasons, hold/reopen,
optimistic lock, timeline+audit per transition, deprecated shim, scoping."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import get_sessionmaker
from app.main import app
from app.models import ClientUser, AuditLog, BusinessUnit, Consent, Membership, Tenant, User
from app.models_staffing import Application, Candidate, CandidateTimeline, Client, Job

HOST = {"host": "spstechnosoft.com"}
PW = "PipeLocal!123"
RECRUITER = "pipe-rec@local.test"

# the full legal happy path, in order (RTR recorded before the submit hop)
HAPPY_PATH = ["screening", "aptitude_test", "aptitude_passed", "internal_interview",
              "internal_passed", "rtr_pending", "submitted_to_client", "client_round_1",
              "offer", "offer_accepted", "joined", "guarantee", "invoiced", "paid"]

ILLEGAL_SAMPLES = [  # (from-chain-position stage, illegal target)
    ("applied", "offer"), ("applied", "joined"), ("screening", "submitted_to_client"),
    ("aptitude_test", "internal_passed"), ("rtr_pending", "client_round_1"),
]


def _mk_user(db, tenant, email, roles):
    # leftover-robust: delete a prior user's memberships/client bindings first
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Pipe Tester", status="active")
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
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _mk_app(c, phone="9833300001"):
    job = c.post("/api/jobs", json={"title": "Pipe Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Pipe Cand", "phone": phone},
                  headers=HOST).json()
    appn = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                  headers=HOST).json()
    return cand["id"], appn["id"]


def _t(c, aid, to_stage, version, reason=None, **hdr):
    body = {"to_stage": to_stage, "expected_version": version}
    if reason:
        body["reason"] = reason
    return c.post(f"/api/applications/{aid}/transition", json=body, headers={**HOST, **hdr})


def test_full_happy_path_with_rtr_gate(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _mk_app(c)
    v = 1
    for stage in HAPPY_PATH:
        if stage == "submitted_to_client":
            blocked = _t(c, aid, stage, v)          # RTR not recorded yet
            assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "RTR_REQUIRED"
            assert c.post(f"/api/applications/{aid}/rtr", headers=HOST).status_code == 200
        r = _t(c, aid, stage, v)
        assert r.status_code == 200, f"{stage}: {r.text}"
        v = r.json()["version"]
    assert r.json()["stage"] == "paid" and v == 1 + len(HAPPY_PATH)
    # terminal: nothing moves out of paid
    assert _t(c, aid, "applied", v).status_code == 409
    # RTR consent ledger row appended (purpose 'rtr')
    db = get_sessionmaker()()
    n = db.execute(select(func.count()).select_from(Consent)
                   .where(Consent.subject_candidate_id == uuid.UUID(cid),
                          Consent.purpose == "rtr")).scalar_one()
    db.close()
    assert n == 1


@pytest.mark.parametrize("src,target", ILLEGAL_SAMPLES)
def test_illegal_transitions_409(env, src, target):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = 1
    for stage in HAPPY_PATH:                        # walk to src
        if stage == "submitted_to_client":
            c.post(f"/api/applications/{aid}/rtr", headers=HOST)
        if src == "applied":
            break
        r = _t(c, aid, stage, v); v = r.json()["version"]
        if stage == src:
            break
    bad = _t(c, aid, target, v)
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "ILLEGAL_TRANSITION", \
        f"{src}→{target} was allowed"


def test_withdraw_requires_reason_and_is_terminal(env):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    r = _t(c, aid, "screening", 1)
    v = r.json()["version"]
    no_reason = _t(c, aid, "withdrawn", v)
    assert no_reason.status_code == 422 and no_reason.json()["error"]["code"] == "REASON_REQUIRED"
    ok = _t(c, aid, "withdrawn", v, reason="candidate accepted elsewhere")
    assert ok.status_code == 200
    db = get_sessionmaker()()
    a = db.get(Application, uuid.UUID(aid))
    assert a.stage == "withdrawn" and a.drop_reason == "candidate accepted elsewhere"
    db.close()
    assert _t(c, aid, "screening", ok.json()["version"]).status_code == 409  # terminal


def test_drop_from_deep_stage_with_reason(env):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = 1
    for stage in ["screening", "aptitude_test", "aptitude_passed"]:
        v = _t(c, aid, stage, v).json()["version"]
    ok = _t(c, aid, "dropped", v, reason="failed background check")
    assert ok.status_code == 200 and ok.json()["stage"] == "dropped"


def test_hold_then_reopen_returns_to_prior_stage(env):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = _t(c, aid, "screening", 1).json()["version"]
    v = _t(c, aid, "on_hold", v, reason="client budget freeze").json()["version"]
    wrong = _t(c, aid, "aptitude_test", v)          # reopen must return to screening
    assert wrong.status_code == 409
    r = _t(c, aid, "screening", v)
    assert r.status_code == 200 and r.json()["stage"] == "screening"
    db = get_sessionmaker()()
    a = db.get(Application, uuid.UUID(aid))
    assert a.hold_prior_stage is None and a.hold_reason is None   # cleared on reopen
    db.close()


def test_optimistic_lock_stale_version_409(env):
    """Simulates the concurrent-mover race: a second client that loaded version 1,
    attempting a move that is graph-legal from the CURRENT stage (so it passes
    validation and reaches the compare-and-swap) but with the stale version."""
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    first = _t(c, aid, "screening", 1)
    assert first.status_code == 200                  # version is now 2
    stale = _t(c, aid, "aptitude_test", 1)           # legal move, stale version
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_STATE"
    fresh = _t(c, aid, "aptitude_test", 2)           # correct version wins
    assert fresh.status_code == 200 and fresh.json()["version"] == 3


def test_one_timeline_and_audit_row_per_transition_and_idempotent_replay(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _mk_app(c)
    key = f"pipe-idem-{uuid.uuid4()}"
    r1 = _t(c, aid, "screening", 1, **{"Idempotency-Key": key})
    r2 = _t(c, aid, "screening", 1, **{"Idempotency-Key": key})   # replay → cached
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    tl = db.execute(select(func.count()).select_from(CandidateTimeline)
                    .where(CandidateTimeline.candidate_id == uuid.UUID(cid),
                           CandidateTimeline.event_type == "StageChange")).scalar_one()
    au = db.execute(select(func.count()).select_from(AuditLog)
                    .where(AuditLog.tenant_id == sps.id,
                           AuditLog.action == "application.stage_change",
                           AuditLog.entity_id == uuid.UUID(aid))).scalar_one()
    assert tl == 1 and au == 1, f"replay duplicated rows (timeline={tl}, audit={au})"


def test_deprecated_shim_goes_through_guard(env):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    ok = c.patch(f"/api/applications/{aid}/stage", json={"stage": "screening"}, headers=HOST)
    assert ok.status_code == 200 and ok.json()["stage"] == "screening"
    bad = c.patch(f"/api/applications/{aid}/stage", json={"stage": "joined"}, headers=HOST)
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "ILLEGAL_TRANSITION"


def test_scoping_tenant_404_and_client_403(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB7")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB7", slug="testb7", name="Tenant B7"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "pipe-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb7.spstechnosoft.com"}
    try:
        cb = TestClient(app); _login(cb, "pipe-b@local.test", B_HOST)
        r = cb.post(f"/api/applications/{aid}/transition",
                    json={"to_stage": "screening", "expected_version": 1}, headers=B_HOST)
        assert r.status_code == 404, "LEAK: tenant B transitioned tenant A's application"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
    # unauth → 401
    assert TestClient(app).post(f"/api/applications/{aid}/transition",
                                json={"to_stage": "screening", "expected_version": 1},
                                headers=HOST).status_code == 401
