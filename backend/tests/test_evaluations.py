"""B.6 internal evaluation rounds: (round,result)→stage via the guard, TestCompletion,
rollback-on-illegal, THE submit invariant (no shortcut to submitted_to_client), gates."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, InternalEvaluation, Job,
)

HOST = {"host": "spstechnosoft.com"}
PW = "EvalLocal!123"
RECRUITER = "eval-rec@local.test"

# every stage BEFORE the internal rounds are complete — none may reach submit directly
PRE_INTERNAL_STAGES = ["applied", "screening", "aptitude_test", "aptitude_passed",
                       "aptitude_failed", "internal_interview"]
WALK = {"applied": [], "screening": ["screening"],
        "aptitude_test": ["screening", "aptitude_test"],
        "aptitude_passed": ["screening", "aptitude_test", "aptitude_passed"],
        "aptitude_failed": ["screening", "aptitude_test", "aptitude_failed"],
        "internal_interview": ["screening", "aptitude_test", "aptitude_passed",
                               "internal_interview"]}


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Eval Tester", status="active")
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
    db.execute(delete(InternalEvaluation).where(InternalEvaluation.tenant_id == sps.id))
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


def _mk_app(c, phone="9811100001"):
    job = c.post("/api/jobs", json={"title": "Eval Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Eval Cand", "phone": phone},
                  headers=HOST).json()
    appn = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                  headers=HOST).json()
    return cand["id"], appn["id"]


def _t(c, aid, to_stage, version, reason=None):
    body = {"to_stage": to_stage, "expected_version": version}
    if reason:
        body["reason"] = reason
    return c.post(f"/api/applications/{aid}/transition", json=body, headers=HOST)


def _walk_to(c, aid, stage):
    v = 1
    for st in WALK[stage]:
        r = _t(c, aid, st, v)
        assert r.status_code == 200, (st, r.text)
        v = r.json()["version"]
    return v


def _eval(c, aid, round_, result, notes=None, **hdr):
    return c.post(f"/api/applications/{aid}/evaluations",
                  json={"round": round_, "result": result, "notes": notes},
                  headers={**HOST, **hdr})


def test_r1_pass_and_fail(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _mk_app(c)
    _walk_to(c, aid, "aptitude_test")
    r = _eval(c, aid, 1, "pass", notes="score 82%")
    assert r.status_code == 200 and r.json()["stage"] == "aptitude_passed"
    tc = c.get(f"/api/candidates/{cid}/timeline", headers=HOST,
               params={"event_type": "TestCompletion"}).json()
    assert len(tc) == 1 and tc[0]["payload"] == {"application_id": aid, "round": 1, "result": "pass"}

    cid2, aid2 = _mk_app(c, phone="9811100002")
    _walk_to(c, aid2, "aptitude_test")
    r = _eval(c, aid2, 1, "fail")
    assert r.status_code == 200 and r.json()["stage"] == "aptitude_failed"


def test_r2_pass_and_fail_via_guard(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = _walk_to(c, aid, "aptitude_passed")
    assert _t(c, aid, "internal_interview", v).status_code == 200
    r = _eval(c, aid, 2, "pass", notes="strong system design")
    assert r.status_code == 200 and r.json()["stage"] == "internal_passed"

    _cid2, aid2 = _mk_app(c, phone="9811100003")
    v = _walk_to(c, aid2, "aptitude_passed")
    assert _t(c, aid2, "internal_interview", v).status_code == 200
    r = _eval(c, aid2, 2, "fail")
    assert r.status_code == 200 and r.json()["stage"] == "dropped"
    a = db.get(Application, uuid.UUID(aid2))
    db.refresh(a)
    assert a.drop_reason == "failed internal technical"     # guard's drop path, not a direct write


@pytest.mark.parametrize("stage", PRE_INTERNAL_STAGES)
def test_invariant_no_shortcut_to_submit(env, stage):
    """THE B.6 invariant: from every pre-internal stage, submitted_to_client is
    unreachable directly — only the full R1+R2+RTR path gets there."""
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = _walk_to(c, aid, stage)
    r = _t(c, aid, "submitted_to_client", v)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ILLEGAL_TRANSITION", \
        f"shortcut from {stage} to submit was allowed"


def test_full_legit_path_succeeds(env):
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    v = _walk_to(c, aid, "aptitude_test")
    v = _eval(c, aid, 1, "pass").json()["version"]
    v = _t(c, aid, "internal_interview", v).json()["version"]
    v = _eval(c, aid, 2, "pass").json()["version"]
    v = _t(c, aid, "rtr_pending", v).json()["version"]
    blocked = _t(c, aid, "submitted_to_client", v)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "RTR_REQUIRED"
    assert c.post(f"/api/applications/{aid}/rtr", headers=HOST).status_code == 200
    ok = _t(c, aid, "submitted_to_client", v)
    assert ok.status_code == 200 and ok.json()["stage"] == "submitted_to_client"


def test_illegal_evaluation_rolls_back_record(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    _walk_to(c, aid, "screening")
    r = _eval(c, aid, 2, "pass")                    # R2 while at screening → illegal
    assert r.status_code == 409 and r.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    n = db.execute(select(func.count()).select_from(InternalEvaluation)
                   .where(InternalEvaluation.application_id == uuid.UUID(aid))).scalar_one()
    assert n == 0, "evaluation row survived an illegal transition (rollback broken)"


def test_record_persisted_and_idempotent_replay(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid = _mk_app(c)
    _walk_to(c, aid, "aptitude_test")
    key = f"eval-idem-{uuid.uuid4()}"
    r1 = _eval(c, aid, 1, "pass", notes="82%", **{"Idempotency-Key": key})
    r2 = _eval(c, aid, 1, "pass", notes="82%", **{"Idempotency-Key": key})   # replay
    assert r1.status_code == 200 and r2.status_code == 200 and r1.json() == r2.json()
    rows = db.execute(select(InternalEvaluation)
                      .where(InternalEvaluation.application_id == uuid.UUID(aid))).scalars().all()
    assert len(rows) == 1 and rows[0].round == 1 and rows[0].result == "pass"
    assert rows[0].notes == "82%" and rows[0].evaluator_id is not None
    tc = db.execute(select(func.count()).select_from(CandidateTimeline)
                    .where(CandidateTimeline.candidate_id == uuid.UUID(cid),
                           CandidateTimeline.event_type == "TestCompletion")).scalar_one()
    assert tc == 1, "replay duplicated the TestCompletion event"


def test_gates(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid = _mk_app(c)
    # unauth → 401
    assert TestClient(app).post(f"/api/applications/{aid}/evaluations",
                                json={"round": 1, "result": "pass"},
                                headers=HOST).status_code == 401
    # tenant B → 404
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB8")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB8", slug="testb8", name="Tenant B8"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "eval-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb8.spstechnosoft.com"}
    try:
        cb = TestClient(app); _login(cb, "eval-b@local.test", B_HOST)
        assert cb.post(f"/api/applications/{aid}/evaluations",
                       json={"round": 1, "result": "pass"}, headers=B_HOST).status_code == 404
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
    # client session → 403
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Eval ClientCo")
    db.add(client); db.flush()
    u = User(tenant_id=sps.id, email="eval-client@local.test",
             password_hash=PasswordHasher().hash(PW), full_name="EC", status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id, status="active"))
    db.commit()
    try:
        cc = TestClient(app); _login(cc, "eval-client@local.test")
        assert cc.post(f"/api/applications/{aid}/evaluations",
                       json={"round": 1, "result": "pass"}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.execute(delete(Client).where(Client.id == client.id)); db.commit()
