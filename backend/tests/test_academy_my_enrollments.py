"""FE#4 — GET /academy/students/me/enrollments. The student sees ONLY their own
enrolments (derived from the session), never another student's, and never a test's
contents. Cross-student isolation is the load-bearing property."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import Tenant
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Test
from app.security import hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadEnr!1234"
EP = "/api/academy/students/me/enrollments"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []

    def student(tag: str) -> Student:
        s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name=f"E4 {tag}",
                    email=f"e4-{tag}-{uuid.uuid4().hex[:6]}@local.test",
                    password_hash=hash_password(PW))
        db.add(s); db.flush(); made.append(s)
        return s

    def enroll(s: Student, status="applied", **kw) -> Enrollment:
        course = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title=f"E4 Course {uuid.uuid4().hex[:4]}",
                        slug=f"e4-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(course); db.flush(); made.append(course)
        cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id, name="B")
        db.add(cohort); db.flush(); made.append(cohort)
        e = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                       student_id=s.id, course_id=course.id, status=status, **kw)
        db.add(e); db.flush(); made.append(e)
        return e

    def test_row(e: Enrollment, s: Student, status="issued", submitted=False, valid_days=3) -> Test:
        t = Test(tenant_id=sps.id, business_unit_id="ACADEMY", enrollment_id=e.id, student_id=s.id,
                 application_id=None, candidate_id=None, link_token_hash=f"h-{uuid.uuid4()}",
                 valid_until=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=valid_days),
                 status=status, served_questions=[{"qid": "x", "stem": "s", "options": ["a"], "correct": 0}],
                 submitted_at=dt.datetime.now(dt.timezone.utc) if submitted else None)
        db.add(t); db.flush(); made.append(t)
        return t

    db.commit()
    yield sps, db, student, enroll, test_row
    for obj in reversed(made):
        db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _login(s: Student) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/academy/auth/login", json={"email": s.email, "password": PW}, headers=HOST)
    assert r.status_code == 200, r.text
    return c


def test_cross_student_isolation(env):
    """A's session returns ONLY A's enrolment; B's data is unreachable — there is NO
    param by which A could select B (the endpoint takes none)."""
    sps, db, student, enroll, _ = env
    a, b = student("A"), student("B")
    ea = enroll(a, status="offered", aptitude_score=90, discount_percent=15, final_fee=42500)
    eb = enroll(b, status="active", aptitude_score=99, discount_percent=20, final_fee=40000)
    db.commit()

    body = _login(a).get(EP, headers=HOST).json()
    ids = {row["enrollment_id"] for row in body}
    assert ids == {str(ea.id)}                              # ONLY A's
    assert str(eb.id) not in ids                            # never B's
    # no B fields leak (B's 99/40000 must not appear anywhere in A's response)
    import json
    blob = json.dumps(body)
    assert "40000" not in blob and str(eb.id) not in blob and b.email not in blob


def test_gate_requires_academy_session(env):
    sps, db, student, enroll, _ = env
    # no session
    assert TestClient(app).get(EP, headers=HOST).status_code == 401
    # a STAFF cookie is not an academy session (A3 two-auth: distinct secret)
    from app.security import create_access_token
    staff = TestClient(app)
    staff.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()),
                      "tenant_id": str(sps.id), "role": "admin"}))
    assert staff.get(EP, headers=HOST).status_code == 401   # no academy_access_token → bounced


def test_no_answer_leak(env):
    sps, db, student, enroll, test_row = env
    s = student("A"); e = enroll(s, status="applied"); test_row(e, s, status="issued")
    db.commit()
    body = _login(s).get(EP, headers=HOST).json()
    import json
    blob = json.dumps(body).lower()
    for banned in ("served_questions", "stem", "options", "correct", "link_token", "token"):
        assert banned not in blob                            # only status/score/fee + active_test presence
    assert body[0]["active_test"] is not None and "valid_until" in body[0]["active_test"]


def test_active_test_lifecycle(env):
    sps, db, student, enroll, test_row = env
    s = student("A"); e = enroll(s, status="applied")
    # issued + unsubmitted + unexpired → surfaces
    t = test_row(e, s, status="issued"); db.commit()
    assert _login(s).get(EP, headers=HOST).json()[0]["active_test"] is not None
    # submitted → gone
    t.status = "submitted"; t.submitted_at = dt.datetime.now(dt.timezone.utc); db.commit()
    assert _login(s).get(EP, headers=HOST).json()[0]["active_test"] is None
    # a fresh expired test → gone
    t.status = "issued"; t.submitted_at = None
    t.valid_until = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1); db.commit()
    assert _login(s).get(EP, headers=HOST).json()[0]["active_test"] is None


def test_null_safe_applied_enrolment(env):
    sps, db, student, enroll, _ = env
    s = student("A"); enroll(s, status="applied")     # no score/discount/fee yet
    db.commit()
    row = _login(s).get(EP, headers=HOST).json()[0]
    assert row["status"] == "applied"
    assert row["aptitude_score"] is None and row["discount_percent"] is None and row["final_fee"] is None
