"""A6 payment activation (stub) — idempotent activation is the property this slice
lives on. Amount is READ off enrollment.final_fee (never recomputed); the confirm
is idempotent per PAYMENT ROW (redelivery = no-op) but a distinct second payment
against an activated enrolment is a caught conflict.
"""
from __future__ import annotations

import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from moto import mock_aws
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Notification, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.models_staffing import Test

HOST = {"host": "spstechnosoft.com"}
PW = "AcadPay!1234"
STAFF = "a6-staff@local.test"


def _mk_staff(db, sps):
    old = db.execute(select(User).where(User.tenant_id == sps.id,
                                        User.email == STAFF)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW),
             full_name="A6 Staff", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["recruiter"]))
    db.commit()
    return u


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
        yield boto3.client("s3", region_name=settings.aws_region)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    staff = _mk_staff(db, sps)

    def make(fee=50000, status="offered", final_fee=None, discount=20, score=95.0):
        course = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title="A6 Course",
                        slug=f"a6-{uuid.uuid4().hex[:8]}", fee=fee)
        student = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="A6 Student",
                          email=f"a6-{uuid.uuid4().hex[:6]}@local.test")
        db.add_all([course, student]); db.flush()
        cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id, name="B")
        db.add(cohort); db.flush()
        enr = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                         student_id=student.id, course_id=course.id, status=status,
                         aptitude_score=score, discount_percent=discount,
                         final_fee=final_fee if final_fee is not None else fee * (100 - discount) / 100)
        db.add(enr); db.commit()
        return enr, student, course

    yield sps, db, staff, make
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id))
    db.execute(delete(Payment).where(Payment.tenant_id == sps.id))
    db.execute(delete(Test).where(Test.tenant_id == sps.id, Test.business_unit_id == "ACADEMY"))
    db.execute(delete(Enrollment).where(Enrollment.tenant_id == sps.id))
    db.execute(delete(Cohort).where(Cohort.tenant_id == sps.id))
    db.execute(delete(Student).where(Student.tenant_id == sps.id, Student.email.like("a6-%")))
    db.execute(delete(Course).where(Course.tenant_id == sps.id, Course.slug.like("a6-%")))
    db.execute(delete(Membership).where(Membership.user_id == staff.id))
    db.execute(delete(User).where(User.id == staff.id))
    db.commit(); db.close()


def _staff_client():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": STAFF, "password": PW},
                  headers=HOST).status_code == 200
    return c


def _pay(c, enr_id):
    return c.post(f"/api/academy/enrollments/{enr_id}/pay", headers=HOST)


def _emails(db, pay_id):
    return db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:payment_confirmed:{pay_id}")).scalar_one()


def test_amount_reads_final_fee_not_recomputed(env, s3):
    sps, db, staff, make = env
    enr, student, course = make(fee=47777, final_fee=12345.67)   # deliberately mismatched
    c = _staff_client()
    r = _pay(c, enr.id)
    assert r.status_code == 200, r.text
    pay = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
    assert float(pay.amount) == 12345.67                        # == final_fee, NOT fee×(100−d)/100


def test_create_idempotency_one_open_row(env):
    sps, db, staff, make = env
    enr, student, course = make(fee=50000)
    from app.routers.academy import _create_or_get_payment
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="ACADEMY", user_id=None,
                         roles=("recruiter",))
    p1 = _create_or_get_payment(db, enr, ctx); db.flush()
    p2 = _create_or_get_payment(db, enr, ctx)
    assert p1.id == p2.id                                        # same open row, no duplicate
    db.rollback()


def test_happy_path_activates_with_receipt_and_email(env, s3):
    sps, db, staff, make = env
    enr, student, course = make(fee=50000)                      # final_fee 40000
    c = _staff_client()
    r = _pay(c, enr.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "paid" and body["paid_at"] is not None
    assert body["enrollment_status"] == "active" and body["receipt_url"]   # offered→active + receipt
    db.expire_all()
    pay = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
    assert float(pay.amount) == 40000.0 and pay.paid_at is not None and pay.receipt_s3_key
    enr2 = db.get(Enrollment, enr.id)
    assert enr2.status == "active" and enr2.payment_status == "paid" and enr2.payment_id == pay.id
    assert _emails(db, pay.id) == 1                              # confirmation email enqueued


def test_double_confirm_redelivery_is_noop(env, s3):
    """The load-bearing test: a SECOND confirm of the SAME (paid) payment — webhook
    redelivery — is a no-op success. No double-activate, no 2nd receipt, no 2nd email."""
    sps, db, staff, make = env
    enr, student, course = make(fee=50000)
    c = _staff_client()
    r1 = _pay(c, enr.id); assert r1.status_code == 200
    db.expire_all()
    pay = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
    key1, paid1 = pay.receipt_s3_key, pay.paid_at
    r2 = _pay(c, enr.id)                                         # redelivery
    assert r2.status_code == 200 and r2.json()["status"] == "paid"
    db.expire_all()
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == enr.id)).scalar_one() == 1     # NO second payment row
    pay2 = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
    assert pay2.receipt_s3_key == key1 and pay2.paid_at == paid1  # not re-activated
    assert _emails(db, pay.id) == 1                              # NO second email


def test_wrong_state_confirm_on_tested_is_4xx(env):
    sps, db, staff, make = env
    enr, student, course = make(fee=50000, status="tested")     # graded but not offered? guard anyway
    c = _staff_client()
    r = _pay(c, enr.id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "STATUS_INVALID"
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == enr.id)).scalar_one() == 0     # nothing minted


def test_second_payment_conflict_against_active_enrollment(env, s3):
    """Distinct from redelivery: enrolment activated by P1; a distinct still-unpaid
    P2 confirm against the now-active enrolment → 4xx conflict, fail-closed."""
    sps, db, staff, make = env
    enr, student, course = make(fee=50000)
    c = _staff_client()
    assert _pay(c, enr.id).status_code == 200                   # P1 activates
    db.expire_all()
    # forge a distinct open P2 created AFTER P1 (the two-payments race)
    p2 = Payment(tenant_id=sps.id, business_unit_id="ACADEMY", enrollment_id=enr.id,
                 amount=40000, currency="INR", status="created", provider="stub")
    db.add(p2); db.commit()
    r = _pay(c, enr.id)                                          # latest = P2 (open), enr active
    assert r.status_code == 409 and r.json()["error"]["code"] == "STATUS_INVALID"
    db.expire_all()
    assert db.execute(select(Payment.status).where(Payment.id == p2.id)).scalar_one() == "created"


def test_create_against_active_enrollment_is_4xx(env):
    sps, db, staff, make = env
    enr, student, course = make(fee=50000, status="active")
    enr.payment_status = "paid"; db.commit()
    from app.routers.academy import _create_or_get_payment
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="ACADEMY", user_id=None,
                         roles=("recruiter",))
    with pytest.raises(HTTPException) as ei:
        _create_or_get_payment(db, enr, ctx)
    assert ei.value.status_code == 409 and ei.value.detail["code"] == "ENROLLMENT_NOT_PAYABLE"
    assert db.execute(select(func.count()).select_from(Payment).where(
        Payment.enrollment_id == enr.id)).scalar_one() == 0     # no row minted


def test_no_tax_added_amount_equals_final_fee(env, s3):
    sps, db, staff, make = env
    enr, student, course = make(fee=49999, final_fee=42499.15)  # A5 15% of 49999
    c = _staff_client()
    _pay(c, enr.id)
    pay = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
    assert float(pay.amount) == 42499.15                        # pre-tax, no GST/TDS folded in
