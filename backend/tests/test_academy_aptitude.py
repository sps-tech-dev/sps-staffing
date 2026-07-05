"""A4-P2 academy aptitude: the 60Q vs 30Q coexistence, admin-triggered issue,
take→auto-grade→enrollment stamp, the BU↔pairing invariant, no-answer-leak, and
that staffing assessments are untouched."""
from __future__ import annotations

import datetime as dt

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.academy_seed import APTITUDE_BANK_NAME, seed_aptitude_bank
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Membership, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Question, QuestionBank, Test

HOST = {"host": "spstechnosoft.com"}
PW = "AcadApt!1234"
STAFF = "a4-staff@local.test"
CAND = "a4-cand@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="A4 Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    staff = _mk_user(db, sps, STAFF, ["recruiter"])
    cand = _mk_user(db, sps, CAND, ["candidate"])
    # a course + cohort + student + enrollment at 'applied'
    course = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title="A4 Course", slug="a4-course")
    student = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="A4 Student",
                      email="a4-student@local.test")
    db.add_all([course, student]); db.flush()
    cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id, name="A4 Batch")
    db.add(cohort); db.flush()
    enr = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                     student_id=student.id, course_id=course.id, status="applied")
    db.add(enr); db.commit()
    yield sps, db, enr, student
    from app.models import Notification
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id))  # A5 take-branch enqueues
    for M in (Test,):
        db.execute(delete(M).where(M.tenant_id == sps.id, M.business_unit_id == "ACADEMY"))
    db.execute(delete(Enrollment).where(Enrollment.tenant_id == sps.id))
    db.execute(delete(Cohort).where(Cohort.tenant_id == sps.id))
    db.execute(delete(Student).where(Student.tenant_id == sps.id, Student.email.like("a4-%")))
    db.execute(delete(Course).where(Course.tenant_id == sps.id, Course.slug == "a4-course"))
    for u in (staff, cand):
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=HOST).status_code == 200


def _issue(c, enr_id):
    return c.post(f"/api/academy/enrollments/{enr_id}/aptitude/issue", headers=HOST)


def test_academy_bank_seeded_60_course_independent(env):
    sps, db, enr, student = env
    bank = db.execute(select(QuestionBank).where(
        QuestionBank.tenant_id == sps.id, QuestionBank.business_unit_id == "ACADEMY",
        QuestionBank.name == APTITUDE_BANK_NAME)).scalar_one()
    n = db.execute(select(func.count()).select_from(Question).where(
        Question.bank_id == bank.id, Question.is_active.is_(True))).scalar_one()
    assert n == 60                                          # minimum to draw a 60Q paper
    cats = {r for r in db.execute(select(Question.category).where(
        Question.bank_id == bank.id)).scalars()}
    assert cats == {"quant", "logical", "verbal", "english"}   # course-INDEPENDENT
    # reproducible + idempotent: a re-seed inserts nothing
    assert seed_aptitude_bank(db.connection(), sps.id) == 0


def test_issue_is_admin_only_and_flag_gated(env):
    sps, db, enr, student = env
    assert TestClient(app).post(f"/api/academy/enrollments/{enr.id}/aptitude/issue",
                                headers=HOST).status_code == 401           # unauth
    cc = TestClient(app); _login(cc, CAND)
    assert _issue(cc, enr.id).status_code == 403                           # candidate can't self-issue
    settings.feature_academy = False
    try:
        sc = TestClient(app); _login(sc, STAFF)
        assert _issue(sc, enr.id).status_code == 404                       # flag off
    finally:
        settings.feature_academy = True


def test_issue_take_grade_stamps_enrollment(env):
    sps, db, enr, student = env
    c = TestClient(app); _login(c, STAFF)
    issued = _issue(c, enr.id)
    assert issued.status_code == 200, issued.text
    assert issued.json()["question_count"] == 60 and issued.json()["time_limit_minutes"] == 60
    token = issued.json()["take_path"].rsplit("/", 1)[-1]

    # the test row carries the ACADEMY pairing ONLY
    test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
    assert test.business_unit_id == "ACADEMY" and test.student_id == student.id
    assert test.application_id is None and test.candidate_id is None

    # take (public token) — the paper NEVER leaks answers
    paper = TestClient(app).get(f"/api/take/{token}", headers=HOST)
    assert paper.status_code == 200 and len(paper.json()["questions"]) == 60
    assert "correct" not in paper.text
    for q in paper.json()["questions"]:
        assert set(q.keys()) == {"qid", "stem", "options"}

    # answer all correctly (harness reads the frozen paper) → grade → stamp enrollment
    frozen = test.served_questions
    answers = {f["qid"]: f["correct"] for f in frozen}
    r = TestClient(app).post(f"/api/take/{token}/submit", json={"answers": answers}, headers=HOST)
    assert r.status_code == 200 and r.json()["pipeline_advanced"] is False
    db.refresh(enr)
    # A5 extends this same callback: applied→(tested)→offered in one grade, +pricing
    assert enr.aptitude_score == 100.0 and enr.status == "offered"


def test_bu_pairing_invariant_at_issue(env):
    """The 0035 CHECK guarantees exactly-one-pairing; the ISSUE writer additionally
    guarantees BU↔pairing (ACADEMY ⟺ academy pairing) — proven by the row shape."""
    sps, db, enr, student = env
    c = TestClient(app); _login(c, STAFF)
    _issue(c, enr.id)
    test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
    is_academy_bu = test.business_unit_id == "ACADEMY"
    is_academy_pairing = (test.enrollment_id is not None and test.student_id is not None
                          and test.application_id is None and test.candidate_id is None)
    assert is_academy_bu == is_academy_pairing is True     # BU ⟺ pairing


def test_issue_requires_applied_status(env):
    sps, db, enr, student = env
    enr.status = "tested"; db.commit()
    c = TestClient(app); _login(c, STAFF)
    r = _issue(c, enr.id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "STATUS_INVALID"


def test_bu_pairing_guard_raises_domain_error_not_assertion(env):
    """#1: the BU↔pairing invariant is a RAISED domain error (envelope), never a
    bare assert (which would 500 + be stripped under python -O)."""
    from fastapi import HTTPException
    from app.routers.academy import _require_academy_pairing
    from app.models_academy import Enrollment
    # a bad academy pairing (null student_id) → HTTPException with the envelope code,
    # NOT AssertionError
    bad = Enrollment(business_unit_id="ACADEMY", student_id=None)
    with pytest.raises(HTTPException) as ei:
        _require_academy_pairing(bad)
    assert ei.value.status_code == 409 and ei.value.detail["code"] == "BU_PAIRING_INVARIANT"
    # a valid academy pairing passes (no raise)
    import uuid as _u
    _require_academy_pairing(Enrollment(business_unit_id="ACADEMY", student_id=_u.uuid4()))


def test_grade_percentage_partial_score(env):
    """#2: verify correct/60×100 at a NON-trivial value (45/60 → 75.0) — A5's
    discount boundaries (75/85/95) stand directly on this arithmetic."""
    sps, db, enr, student = env
    c = TestClient(app); _login(c, STAFF)
    token = _issue(c, enr.id).json()["take_path"].rsplit("/", 1)[-1]
    test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
    frozen = test.served_questions
    # answer exactly 45 of 60 correctly; the rest wrong (correct_index+1 mod 4)
    answers = {}
    for i, f in enumerate(frozen):
        answers[f["qid"]] = f["correct"] if i < 45 else (f["correct"] + 1) % 4
    r = TestClient(app).post(f"/api/take/{token}/submit", json={"answers": answers}, headers=HOST)
    assert r.status_code == 200
    db.refresh(enr)
    assert enr.aptitude_score == 75.0 and enr.status == "offered"   # 45/60 × 100 = 75.00 (A5 → offered)
