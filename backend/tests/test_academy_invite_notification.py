"""FE#4b — aptitude-invite notification + the student notification read.
Cross-student isolation is load-bearing: the invite's vars.take_link is a LIVE
one-time test token, so student A must NEVER read B's notifications."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.main import app
from app.models import Notification, Tenant
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Test
from app.security import hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadInv!1234"
NOTIF_EP = "/api/academy/students/me/notifications"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []

    def student(tag):
        s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name=f"Inv {tag}",
                    email=f"inv-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
        db.add(s); db.flush(); made.append(s)
        course = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title=f"Inv Course {tag}",
                        slug=f"inv-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(course); db.flush(); made.append(course)
        cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id, name="B")
        db.add(cohort); db.flush(); made.append(cohort)
        e = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                       student_id=s.id, course_id=course.id, status="applied")
        db.add(e); db.flush(); made.append(e)
        return s, e

    db.commit()
    yield sps, db, student, made
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id,
               Notification.template_code == "academy_aptitude_invite"))
    for obj in reversed(made):
        db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _issue(db, sps, e):
    """Admin issues an aptitude test → enqueues the invite. Returns the raw token."""
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="ACADEMY", user_id=None, roles=("recruiter",))
    from app.routers.academy import issue_aptitude
    return issue_aptitude(enrollment_id=e.id, ctx=ctx, db=db, idempotency_key=None)["take_path"]


def _login(s):
    c = TestClient(app)
    assert c.post("/api/academy/auth/login", json={"email": s.email, "password": PW}, headers=HOST).status_code == 200
    return c


def test_invite_enqueued_at_issue_with_take_link(env):
    sps, db, student, _ = env
    s, e = student("A")
    take_path = _issue(db, sps, e)
    token = take_path.rsplit("/", 1)[-1]
    n = db.execute(select(Notification).where(
        Notification.idempotency_key == f"academy:aptitude_invite:{db.execute(select(Test.id).where(Test.enrollment_id == e.id)).scalar_one()}")).scalar_one()
    assert n.template_code == "academy_aptitude_invite" and n.recipient == s.email
    assert n.vars.get("take_link") == f"/take/{token}"          # the live link is in the addressed row


def test_cross_student_notification_isolation(env):
    """LOAD-BEARING: A's read returns only A's invite; B's take token never appears."""
    sps, db, student, _ = env
    a, ea = student("A"); b, eb = student("B")
    _issue(db, sps, ea); tb = _issue(db, sps, eb)
    db.commit()
    b_token = tb.rsplit("/", 1)[-1]

    body = _login(a).get(NOTIF_EP, headers=HOST).json()
    import json
    blob = json.dumps(body)
    assert all(row["recipient"] if "recipient" in row else True for row in body)  # shape
    assert b_token not in blob and b.email not in blob          # B's LIVE token never leaks to A
    # A sees exactly one invite, and it's A's own
    invites = [r for r in body if r["template_code"] == "academy_aptitude_invite"]
    assert len(invites) == 1 and invites[0]["take_link"].startswith("/take/")


def test_notification_read_gate(env):
    sps, db, student, _ = env
    assert TestClient(app).get(NOTIF_EP, headers=HOST).status_code == 401     # no session
    from app.security import create_access_token
    staff = TestClient(app)
    staff.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()),
                      "tenant_id": str(sps.id), "role": "admin"}))
    assert staff.get(NOTIF_EP, headers=HOST).status_code == 401              # staff cookie ≠ academy session


def test_invite_idempotent_on_test(env):
    sps, db, student, _ = env
    s, e = student("A")
    _issue(db, sps, e)                                          # attempt 1 → one invite
    test1 = db.execute(select(Test).where(Test.enrollment_id == e.id)).scalar_one()
    n1 = db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:aptitude_invite:{test1.id}")).scalar_one()
    assert n1 == 1
    # a fresh RETAKE (submit attempt 1 as fail path not needed — just clear active + re-issue)
    db.execute(delete(Test).where(Test.id == test1.id)); db.commit()
    e2 = db.get(Enrollment, e.id); e2.status = "applied"; db.commit()
    _issue(db, sps, e)                                          # new test = new token = new invite
    test2 = db.execute(select(Test).where(Test.enrollment_id == e.id)).scalar_one()
    assert test2.id != test1.id
    n2 = db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:aptitude_invite:{test2.id}")).scalar_one()
    assert n2 == 1                                              # a new invite for the new test


def test_enrollments_endpoint_still_no_token(env):
    """The token lives ONLY in the addressed notification — the enrolments read stays
    presence-only."""
    sps, db, student, _ = env
    s, e = student("A")
    take = _issue(db, sps, e); db.commit()
    token = take.rsplit("/", 1)[-1]
    body = _login(s).get("/api/academy/students/me/enrollments", headers=HOST).json()
    import json
    assert token not in json.dumps(body)                       # no token in the enrolments endpoint
    assert body[0]["active_test"] is not None                  # presence still surfaces
