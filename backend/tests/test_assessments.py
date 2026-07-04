"""B.7 aptitude engine: freeze/no-answer-leak/grade, token lifecycle + isolation,
double-emitter safety, idempotent submit, retake cooldown, snapshots, gates."""
from __future__ import annotations

import datetime as dt
import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, func, select, text

from app import assessment_engine as engine
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, InternalEvaluation, Job, Question, Test,
)

HOST = {"host": "spstechnosoft.com"}
PW = "TestLocal!123"
RECRUITER = "apt-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Apt Tester", status="active")
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
    db.execute(delete(Test).where(Test.tenant_id == sps.id))
    db.execute(delete(InternalEvaluation).where(InternalEvaluation.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Application, Job, Candidate, Client):  # seed banks/questions stay!
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _app_at_aptitude(c, phone="9801100001"):
    job = c.post("/api/jobs", json={"title": "Apt Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Apt Cand", "phone": phone},
                  headers=HOST).json()
    aid = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                 headers=HOST).json()["id"]
    v = 1
    for st in ("screening", "aptitude_test"):
        r = c.post(f"/api/applications/{aid}/transition",
                   json={"to_stage": st, "expected_version": v}, headers=HOST)
        assert r.status_code == 200, r.text
        v = r.json()["version"]
    return cand["id"], aid, v


def _issue(c, aid):
    r = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()


def _token(issued):
    return issued["take_path"].rsplit("/", 1)[1]


def _frozen(db, test_id):
    return db.execute(text("SELECT served_questions FROM staffing.tests WHERE id=:i"),
                      {"i": test_id}).scalar_one()


def _all_correct_answers(frozen):
    return {f["qid"]: f["correct"] for f in frozen}


# ── freeze + no-answer-leak ──────────────────────────────────────
def test_issue_freezes_and_fetch_leaks_no_answers(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    assert issued["question_count"] == min(settings.test_question_count, 12)  # 12 seed questions
    frozen = _frozen(db, issued["test_id"])
    assert all("correct" in f for f in frozen)          # answers live server-side

    p = TestClient(app)                                  # candidate: NO login
    r = p.get(f"/api/take/{_token(issued)}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["questions"]) == issued["question_count"]
    assert "correct" not in r.text, "correct answers leaked to the candidate!"
    for q in body["questions"]:
        assert set(q.keys()) == {"qid", "stem", "options"}


def test_grade_boundaries_no_negative_marking():
    frozen = [{"qid": str(i), "stem": "s", "options": ["a", "b"], "correct": 0,
               "difficulty": "easy"} for i in range(10)]
    all_right = {str(i): 0 for i in range(10)}
    score, passed, _ = engine.grade(frozen, all_right)
    assert score == 1.0 and passed
    seven = {str(i): (0 if i < 7 else 1) for i in range(10)}     # exactly 70%
    score, passed, _ = engine.grade(frozen, seven)
    assert score == 0.7 and passed                               # boundary passes (>=)
    six = {str(i): (0 if i < 6 else 1) for i in range(10)}
    score, passed, _ = engine.grade(frozen, six)
    assert score == 0.6 and not passed
    score, passed, _ = engine.grade(frozen, {"garbage": 99})     # missing/invalid = wrong, never negative
    assert score == 0.0 and not passed


def test_freeze_integrity_bank_edits_dont_affect_taken_test(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    frozen = _frozen(db, issued["test_id"])
    # sabotage the bank AFTER issue: flip every correct_index and deactivate all
    db.execute(text("UPDATE staffing.questions SET correct_index = 0, is_active = false "
                    "WHERE tenant_id = :t"), {"t": str(sps.id)})
    db.commit()
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    r = p.post(f"/api/take/{_token(issued)}/submit",
               json={"answers": _all_correct_answers(frozen)})
    assert r.status_code == 200 and r.json()["score"] == 1.0 and r.json()["passed"], \
        "grading was affected by post-issue bank edits — freeze broken"
    # restore the seed for other tests
    db.execute(text("UPDATE staffing.questions SET is_active = true WHERE tenant_id = :t"),
               {"t": str(sps.id)})
    db.commit()


# ── pipeline wiring + double-emitter safety ──────────────────────
def test_submit_drives_pipeline_and_emits_once(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    frozen = _frozen(db, issued["test_id"])
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    r = p.post(f"/api/take/{_token(issued)}/submit",
               json={"answers": _all_correct_answers(frozen)})
    assert r.status_code == 200 and r.json()["pipeline_advanced"] is True
    a = db.get(Application, uuid.UUID(aid)); db.refresh(a)
    assert a.stage == "aptitude_passed"
    events = db.execute(select(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "TestCompletion")).scalars().all()
    assert len(events) == 1 and events[0].payload["source"] == "engine"
    # manual B.6 override AFTER the engine → guard 409s; still exactly one event
    m = c.post(f"/api/applications/{aid}/evaluations",
               json={"round": 1, "result": "pass"}, headers=HOST)
    assert m.status_code == 409


def test_manual_override_first_engine_stores_grade_without_double_fire(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    frozen = _frozen(db, issued["test_id"])
    # staff records R1 manually first (B.6 override path)
    m = c.post(f"/api/applications/{aid}/evaluations",
               json={"round": 1, "result": "pass"}, headers=HOST)
    assert m.status_code == 200
    # candidate submits afterwards: grade stored, pipeline untouched, no 2nd event
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    r = p.post(f"/api/take/{_token(issued)}/submit",
               json={"answers": _all_correct_answers(frozen)})
    assert r.status_code == 200 and r.json()["pipeline_advanced"] is False
    n = db.execute(select(func.count()).select_from(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "TestCompletion")).scalar_one()
    assert n == 1, "TestCompletion double-fired"
    a = db.get(Application, uuid.UUID(aid)); db.refresh(a)
    assert a.stage == "aptitude_passed"                 # manual result stands


def test_idempotent_submit(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    frozen = _frozen(db, issued["test_id"])
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    r1 = p.post(f"/api/take/{_token(issued)}/submit",
                json={"answers": _all_correct_answers(frozen)})
    r2 = p.post(f"/api/take/{_token(issued)}/submit", json={"answers": {}})   # replay w/ junk
    assert r2.status_code == 200 and r2.json()["already_submitted"] is True
    assert float(r2.json()["score"]) == r1.json()["score"] == 1.0             # no re-grade
    n = db.execute(select(func.count()).select_from(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "TestCompletion")).scalar_one()
    assert n == 1


# ── token lifecycle + isolation ──────────────────────────────────
def test_token_lifecycle_and_isolation(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid1, aid1, _ = _app_at_aptitude(c, phone="9801100011")
    _cid2, aid2, _ = _app_at_aptitude(c, phone="9801100012")
    t1, t2 = _issue(c, aid1), _issue(c, aid2)
    p = TestClient(app)
    # unknown token → 404 (no enumeration signal)
    assert p.get("/api/take/definitely-not-a-token").status_code == 404
    # a token reaches ONLY its own test: submitting with t1 leaves app2 untouched
    frozen1 = _frozen(db, t1["test_id"])
    p.get(f"/api/take/{_token(t1)}")
    p.post(f"/api/take/{_token(t1)}/submit", json={"answers": _all_correct_answers(frozen1)})
    a2 = db.get(Application, uuid.UUID(aid2)); db.refresh(a2)
    assert a2.stage == "aptitude_test", "token crossed to another test/application"
    # submitted → re-fetch 410
    assert p.get(f"/api/take/{_token(t1)}").status_code == 410
    # expired → 410
    db.execute(text("UPDATE staffing.tests SET valid_until = now() - interval '1 hour' "
                    "WHERE id = :i"), {"i": t2["test_id"]})
    db.commit()
    assert p.get(f"/api/take/{_token(t2)}").status_code == 410
    # raw token is never stored — only its hash
    stored = db.execute(text("SELECT link_token_hash FROM staffing.tests WHERE id=:i"),
                        {"i": t1["test_id"]}).scalar_one()
    assert stored != _token(t1) and stored == engine.hash_token(_token(t1))


def test_take_requires_token_not_jwt(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)               # staff JWT session
    assert c.get("/api/take/some-invented-token", headers=HOST).status_code == 404, \
        "a JWT must not substitute for the token"


# ── retake cooldown ──────────────────────────────────────────────
def test_retake_cooldown_then_fresh_attempt(env, monkeypatch):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    r = p.post(f"/api/take/{_token(issued)}/submit", json={"answers": {}})    # 0% → fail
    assert r.status_code == 200 and not r.json()["passed"]
    a = db.get(Application, uuid.UUID(aid)); db.refresh(a)
    assert a.stage == "aptitude_failed"
    # staff retake edge: aptitude_failed → aptitude_test
    rr = c.post(f"/api/applications/{aid}/transition",
                json={"to_stage": "aptitude_test", "expected_version": a.version}, headers=HOST)
    assert rr.status_code == 200
    # within cooldown → rejected
    r = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RETAKE_COOLDOWN"
    # after cooldown (config → 0 days) → fresh paper, attempt_no=2
    monkeypatch.setattr(settings, "test_retake_cooldown_days", 0)
    again = _issue(c, aid)
    assert again["attempt_no"] == 2 and again["test_id"] != issued["test_id"]
    assert _token(again) != _token(issued)


def test_one_active_test_at_a_time(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    _issue(c, aid)
    r = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "TEST_ACTIVE"


def test_issue_requires_aptitude_stage(env):
    c = TestClient(app); _login(c, RECRUITER)
    job = c.post("/api/jobs", json={"title": "Stage Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Stage Cand", "phone": "9801100021"},
                  headers=HOST).json()
    aid = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                 headers=HOST).json()["id"]                     # stage = applied
    r = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "STAGE_INVALID"


# ── snapshots (moto) ─────────────────────────────────────────────
@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.storage_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region})
        yield


def test_snapshot_presign_records_key(env, s3):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    p = TestClient(app)
    # before start → 410 (upload only valid during a started test)
    assert p.post(f"/api/take/{_token(issued)}/snapshot/presign", json={}).status_code == 410
    p.get(f"/api/take/{_token(issued)}")                          # start
    r = p.post(f"/api/take/{_token(issued)}/snapshot/presign", json={})
    assert r.status_code == 200
    key = r.json()["key"]
    assert key.startswith(f"tenant={sps.id}/business_unit=STAFFING/candidates/{cid}/proctor/")
    flags = db.execute(text("SELECT proctor_flags FROM staffing.tests WHERE id=:i"),
                       {"i": issued["test_id"]}).scalar_one()
    assert key in flags["snapshots"]
    bad = p.post(f"/api/take/{_token(issued)}/snapshot/presign",
                 json={"content_type": "application/pdf"})
    assert bad.status_code == 422


# ── staff gates + tenant isolation ───────────────────────────────
def test_staff_gates_and_tenant_isolation(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    _issue(c, aid)
    # unauth staff endpoints → 401
    assert TestClient(app).post(f"/api/applications/{aid}/tests/issue",
                                headers=HOST).status_code == 401
    assert TestClient(app).get("/api/tests", headers=HOST).status_code == 401
    # dashboard shows the test, but never the paper/hash
    rows = c.get("/api/tests", headers=HOST, params={"application_id": aid}).json()
    assert len(rows) == 1 and "served_questions" not in rows[0] and "link_token_hash" not in rows[0]
    # tenant B sees nothing
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB9")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB9", slug="testb9", name="Tenant B9"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "apt-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb9.spstechnosoft.com"}
    try:
        cb = TestClient(app); _login(cb, "apt-b@local.test", B_HOST)
        assert cb.get("/api/tests", headers=B_HOST).json() == []
        assert cb.post(f"/api/applications/{aid}/tests/issue", headers=B_HOST).status_code == 404
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
    # client session → 403 on staff endpoints
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Apt ClientCo")
    db.add(client); db.flush()
    u = User(tenant_id=sps.id, email="apt-client@local.test",
             password_hash=PasswordHasher().hash(PW), full_name="AC", status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id, status="active"))
    db.commit()
    try:
        cc = TestClient(app); _login(cc, "apt-client@local.test")
        assert cc.get("/api/tests", headers=HOST).status_code == 403
        assert cc.post(f"/api/applications/{aid}/tests/issue", headers=HOST).status_code == 403
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.execute(delete(Client).where(Client.id == client.id)); db.commit()


# ── admin assessment waiver (FEATURE_ASSESSMENT_WAIVER) ─────────
ADMIN = "apt-admin@local.test"


@pytest.fixture
def admin_env(env):
    sps, db = env
    adm = _mk_user(db, sps, ADMIN, ["admin"])
    yield sps, db
    db.execute(delete(Membership).where(Membership.user_id == adm.id))
    db.execute(delete(User).where(User.id == adm.id))
    db.commit()


def _waive(c, aid, test_id, result="pass", reason="pre-vetted senior referral", **hdr):
    body = {"result": result}
    if reason is not None:
        body["reason"] = reason
    return c.post(f"/api/applications/{aid}/tests/{test_id}/waive",
                  json=body, headers={**HOST, **hdr})


def test_waiver_flag_off_is_404(admin_env):
    sps, db = admin_env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    a = TestClient(app); _login(a, ADMIN)
    assert settings.feature_assessment_waiver is False        # env default OFF
    assert _waive(a, aid, issued["test_id"]).status_code == 404   # probe-proof


def test_waiver_full_flow_and_mutual_exclusion(admin_env, monkeypatch):
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    # ordinary staff → 403 even with the flag on
    assert _waive(c, aid, issued["test_id"]).status_code == 403
    a = TestClient(app); _login(a, ADMIN)
    # missing reason → 422
    r = a.post(f"/api/applications/{aid}/tests/{issued['test_id']}/waive",
               json={"result": "pass"}, headers=HOST)
    assert r.status_code == 422
    # admin + reason → waived pass
    r = _waive(a, aid, issued["test_id"])
    assert r.status_code == 200 and r.json()["waived"] is True and r.json()["passed"] is True
    ap = db.get(Application, uuid.UUID(aid)); db.refresh(ap)
    assert ap.stage == "aptitude_passed"
    row = db.execute(text("SELECT score, passed, proctor_flags FROM staffing.tests WHERE id=:i"),
                     {"i": issued["test_id"]}).one()
    assert row.score is None, "waiver faked a score"
    assert row.passed is True and row.proctor_flags["waived"]["source"] == "admin_waive"
    assert row.proctor_flags["waived"]["reason"] == "pre-vetted senior referral"
    events = db.execute(select(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "TestCompletion")).scalars().all()
    assert len(events) == 1 and events[0].payload["source"] == "admin_waive"
    # dashboard: waived pass is distinguishable (score NULL + waived true)
    dash = c.get("/api/tests", headers=HOST, params={"application_id": aid}).json()[0]
    assert dash["waived"] is True and dash["score"] is None and dash["passed"] is True
    # mutual exclusion: the waived test is closed to the take surface
    p = TestClient(app)
    assert p.get(f"/api/take/{_token(issued)}").status_code == 410
    assert p.post(f"/api/take/{_token(issued)}/submit", json={"answers": {}}).status_code == 410
    # idempotent re-waive → stored result, no dup transition/event
    r2 = _waive(a, aid, issued["test_id"], result="fail", reason="changed my mind")
    assert r2.status_code == 200 and r2.json()["already_waived"] is True and r2.json()["passed"] is True
    db.refresh(ap)
    assert ap.stage == "aptitude_passed"                       # unchanged
    n = db.execute(select(func.count()).select_from(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "TestCompletion")).scalar_one()
    assert n == 1


def test_graded_test_cannot_be_waived(admin_env, monkeypatch):
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    frozen = _frozen(db, issued["test_id"])
    p = TestClient(app)
    p.get(f"/api/take/{_token(issued)}")
    p.post(f"/api/take/{_token(issued)}/submit", json={"answers": _all_correct_answers(frozen)})
    a = TestClient(app); _login(a, ADMIN)
    r = _waive(a, aid, issued["test_id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_GRADED"


def test_invariant_holds_with_waiver(admin_env, monkeypatch):
    """A waived R1 pass does NOT unlock submit — R2 + RTR still required."""
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    a = TestClient(app); _login(a, ADMIN)
    r = _waive(a, aid, issued["test_id"])
    assert r.status_code == 200
    ap = db.get(Application, uuid.UUID(aid)); db.refresh(ap)
    # direct jump to submit from the waived pass → 409
    jump = c.post(f"/api/applications/{aid}/transition",
                  json={"to_stage": "submitted_to_client", "expected_version": ap.version},
                  headers=HOST)
    assert jump.status_code == 409 and jump.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    # only the full R2 + RTR path succeeds
    v = ap.version
    v = c.post(f"/api/applications/{aid}/transition",
               json={"to_stage": "internal_interview", "expected_version": v},
               headers=HOST).json()["version"]
    v = c.post(f"/api/applications/{aid}/evaluations",
               json={"round": 2, "result": "pass"}, headers=HOST).json()["version"]
    v = c.post(f"/api/applications/{aid}/transition",
               json={"to_stage": "rtr_pending", "expected_version": v},
               headers=HOST).json()["version"]
    assert c.post(f"/api/applications/{aid}/rtr", headers=HOST).status_code == 200
    ok = c.post(f"/api/applications/{aid}/transition",
                json={"to_stage": "submitted_to_client", "expected_version": v}, headers=HOST)
    assert ok.status_code == 200


def test_waived_fail_follows_retake_cooldown(admin_env, monkeypatch):
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    a = TestClient(app); _login(a, ADMIN)
    r = _waive(a, aid, issued["test_id"], result="fail", reason="known mismatch")
    assert r.status_code == 200 and r.json()["passed"] is False
    ap = db.get(Application, uuid.UUID(aid)); db.refresh(ap)
    assert ap.stage == "aptitude_failed"
    rr = c.post(f"/api/applications/{aid}/transition",
                json={"to_stage": "aptitude_test", "expected_version": ap.version}, headers=HOST)
    assert rr.status_code == 200
    blocked = c.post(f"/api/applications/{aid}/tests/issue", headers=HOST)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "RETAKE_COOLDOWN"


# ── Step-0 (B.8 carry-over): pin the waiver to admin/owner ONLY ──
@pytest.mark.parametrize("roles", [["recruiter"], ["employee"], ["coordinator"],
                                   ["business_manager"], ["candidate"]])
def test_waiver_boundary_no_staff_role_can_waive(admin_env, monkeypatch, roles):
    """Permanently locks the B.7 waiver: no non-admin STAFF role may waive."""
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    email = f"wb-{roles[0]}@local.test"
    u = _mk_user(db, sps, email, roles)
    try:
        s = TestClient(app); _login(s, email)
        r = _waive(s, aid, issued["test_id"])
        assert r.status_code == 403, f"role {roles} was able to reach the waiver!"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit()


def test_waiver_boundary_client_sessions_blocked(admin_env, monkeypatch):
    """client_admin and client_manager portal sessions can never waive."""
    sps, db = admin_env
    monkeypatch.setattr(settings, "feature_assessment_waiver", True)
    c = TestClient(app); _login(c, RECRUITER)
    _cid, aid, _v = _app_at_aptitude(c)
    issued = _issue(c, aid)
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="WB ClientCo")
    db.add(client); db.flush()
    made = []
    for role in ("client_admin", "client_manager"):
        u = User(tenant_id=sps.id, email=f"wb-{role}@local.test",
                 password_hash=PasswordHasher().hash(PW), full_name="WB", status="active")
        db.add(u); db.flush()
        db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id,
                          status="active", role=role))
        made.append(u)
    db.commit()
    try:
        for role in ("client_admin", "client_manager"):
            s = TestClient(app); _login(s, f"wb-{role}@local.test")
            r = _waive(s, aid, issued["test_id"])
            assert r.status_code == 403, f"{role} was able to reach the waiver!"
    finally:
        for u in made:
            db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
            db.execute(delete(User).where(User.id == u.id))
        db.execute(delete(Client).where(Client.id == client.id)); db.commit()
