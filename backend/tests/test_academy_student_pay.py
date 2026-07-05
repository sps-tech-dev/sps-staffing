"""FE#6 backend — student-INITIATE pay (POST /students/me/enrollments/{id}/pay).
Cross-student isolation is load-bearing (money): student A must NEVER trigger pay
on B's enrolment. The student path and the A6 staff path share `_activate_payment`
byte-for-byte — the split is auth only."""
from __future__ import annotations

import uuid

import boto3
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, func, select

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.main import app
from app.models import Notification, Tenant
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.security import hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadPay6!1234"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


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


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []

    def mk(tag, status="offered", final=40000, disc=20, score=96):
        s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name=f"Pay6 {tag}",
                    email=f"pay6-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title=f"Pay6 {tag}",
                   slug=f"pay6-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=c.id, name="B")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status=status,
                       aptitude_score=score, discount_percent=disc, final_fee=final)
        db.add(e); db.flush(); made.append(e)
        db.commit()          # commit so the student is loginable via a fresh session
        return s, e

    db.commit()
    yield sps, db, mk
    db.execute(delete(Notification).where(Notification.recipient.like("pay6-%")))
    enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
    if enr_ids:
        db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
    for obj in reversed(made):
        db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _login(s):
    c = TestClient(app)
    assert c.post("/api/academy/auth/login", json={"email": s.email, "password": PW},
                  headers=HOST).status_code == 200
    return c


def _pay(client, enr_id):
    return client.post(f"/api/academy/students/me/enrollments/{enr_id}/pay", headers=HOST)


def test_cross_student_pay_isolation(env, s3):
    """LOAD-BEARING (money): A cannot trigger pay on B's enrolment — 404, and B's
    enrolment stays offered/unpaid (nothing activated)."""
    sps, db, mk = env
    a, ea = mk("A"); b, eb = mk("B")
    db.commit()
    r = _pay(_login(a), eb.id)                              # A's session, B's enrolment id
    assert r.status_code == 404                            # fail closed — not B's activation
    db.expire_all()
    eb2 = db.get(Enrollment, eb.id)
    assert eb2.status == "offered" and eb2.payment_status == "pending"   # B untouched
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == eb.id)).scalar_one() == 0


def test_student_pay_happy_and_redelivery_noop(env, s3):
    sps, db, mk = env
    s, e = mk("A")
    c = _login(s)
    r1 = _pay(c, e.id)
    assert r1.status_code == 200 and r1.json()["status"] == "paid"
    assert r1.json()["enrollment_status"] == "active" and r1.json()["receipt_url"]
    db.expire_all()
    pay = db.execute(select(Payment).where(Payment.enrollment_id == e.id)).scalar_one()
    key1 = pay.receipt_s3_key
    n1 = db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one()
    assert n1 == 1
    # redelivery: student re-hits their own paid enrolment → no-op success, NO 2nd activation
    r2 = _pay(c, e.id)
    assert r2.status_code == 200 and r2.json()["status"] == "paid"
    db.expire_all()
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == e.id)).scalar_one() == 1          # no 2nd payment row
    pay2 = db.execute(select(Payment).where(Payment.enrollment_id == e.id)).scalar_one()
    assert pay2.receipt_s3_key == key1                            # not re-activated
    assert db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one() == 1  # no 2nd email


def test_student_pay_wrong_state_409(env, s3):
    sps, db, mk = env
    s, e = mk("A", status="tested")                        # not offered
    r = _pay(_login(s), e.id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "STATUS_INVALID"
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == e.id)).scalar_one() == 0


def test_student_pay_gate(env, s3):
    sps, db, mk = env
    s, e = mk("A")
    # no academy session
    assert TestClient(app).post(
        f"/api/academy/students/me/enrollments/{e.id}/pay", headers=HOST).status_code == 401
    # a staff access_token is not an academy session
    from app.security import create_access_token
    staff = TestClient(app)
    staff.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()),
                      "tenant_id": str(sps.id), "role": "admin"}))
    assert _pay(staff, e.id).status_code == 401


def test_shared_seam_student_and_staff_same_activation(env, s3):
    """The student path and the A6 staff path both enter _activate_payment and
    produce the SAME activation effect — the split is auth only."""
    sps, db, mk = env
    # student path
    s1, e1 = mk("A")
    _pay(_login(s1), e1.id)
    db.expire_all()
    p1 = db.execute(select(Payment).where(Payment.enrollment_id == e1.id)).scalar_one()
    en1 = db.get(Enrollment, e1.id)
    student_effect = (p1.status == "paid" and p1.paid_at is not None and p1.receipt_s3_key
                      and en1.status == "active" and en1.payment_status == "paid"
                      and en1.payment_id == p1.id)
    # staff path (A6 confirm_payment) on a fresh enrolment
    s2, e2 = mk("B")
    from app.routers.academy import confirm_payment
    staff_ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="ACADEMY",
                               user_id=None, roles=("recruiter",))
    confirm_payment(enrollment_id=e2.id, ctx=staff_ctx, db=db)
    db.expire_all()
    p2 = db.execute(select(Payment).where(Payment.enrollment_id == e2.id)).scalar_one()
    en2 = db.get(Enrollment, e2.id)
    staff_effect = (p2.status == "paid" and p2.paid_at is not None and p2.receipt_s3_key
                    and en2.status == "active" and en2.payment_status == "paid"
                    and en2.payment_id == p2.id)
    assert student_effect and staff_effect                 # identical activation via the shared seam
