"""FE#7 (B) — durable receipt read + has_receipt signal. Cross-student isolation
is load-bearing (a presigned PII-document link): student A must NEVER obtain B's
receipt_url, by any param, fail closed."""
from __future__ import annotations

import uuid

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import Tenant
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.security import hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadRcpt!1234"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def s3(monkeypatch):
    # presign signing needs SOME credentials even though it's offline
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

    def mk(tag, *, paid=False, receipt=False):
        """paid+receipt = a genuine #6-paid enrolment; paid without receipt = the
        seeded direct-insert (receipt_s3_key null)."""
        s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name=f"Rcpt {tag}",
                    email=f"rcpt-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title=f"Rcpt {tag}",
                   slug=f"rcpt-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=c.id, name="B")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id,
                       status="active" if paid else "offered",
                       payment_status="paid" if paid else "pending",
                       aptitude_score=96, discount_percent=20, final_fee=40000)
        db.add(e); db.flush(); made.append(e)
        if paid:
            p = Payment(tenant_id=sps.id, business_unit_id="ACADEMY", enrollment_id=e.id,
                        amount=40000, currency="INR", status="paid", provider="stub",
                        receipt_s3_key=(f"tenant={sps.id}/business_unit=ACADEMY/enrollments/{e.id}/"
                                        f"receipts/{uuid.uuid4()}.pdf") if receipt else None)
            db.add(p); db.flush(); made.append(p)
            e.payment_id = p.id
        db.commit()
        return s, e

    yield sps, db, mk
    enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
    if enr_ids:
        db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
    for obj in reversed(made):
        if not isinstance(obj, Payment):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _login(s):
    c = TestClient(app)
    assert c.post("/api/academy/auth/login", json={"email": s.email, "password": PW},
                  headers=HOST).status_code == 200
    return c


def _receipt(client, enr_id):
    return client.get(f"/api/academy/students/me/enrollments/{enr_id}/receipt", headers=HOST)


def test_cross_student_receipt_isolation(env, s3):
    """LOAD-BEARING: A → B's receipt = 404 NOT_FOUND (indistinguishable from
    nonexistent); A never obtains B's receipt_url."""
    sps, db, mk = env
    a, ea = mk("A", paid=True, receipt=True)
    b, eb = mk("B", paid=True, receipt=True)
    r = _receipt(_login(a), eb.id)                          # A's session, B's enrolment id
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert "receipt_url" not in r.text                      # nothing leaked
    # a random nonexistent id → the SAME 404 NOT_FOUND (no existence oracle)
    r2 = _receipt(_login(a), uuid.uuid4())
    assert r2.status_code == 404 and r2.json()["error"]["code"] == "NOT_FOUND"


def test_paid_with_receipt_returns_presigned_url(env, s3):
    sps, db, mk = env
    s, e = mk("A", paid=True, receipt=True)
    r = _receipt(_login(s), e.id)
    assert r.status_code == 200
    assert r.json()["receipt_url"].startswith("http") and "X-Amz-Signature" in r.json()["receipt_url"]


def test_own_unpaid_no_receipt_404_distinct_code(env, s3):
    sps, db, mk = env
    # own enrolment, offered/unpaid → 404 RECEIPT_NOT_AVAILABLE (own rows only)
    s, e = mk("A")                                          # not paid
    r = _receipt(_login(s), e.id)
    assert r.status_code == 404 and r.json()["error"]["code"] == "RECEIPT_NOT_AVAILABLE"
    # own enrolment, PAID but receipt_s3_key null (the seed-shortcut gap) → same distinct 404
    s2, e2 = mk("B", paid=True, receipt=False)
    r2 = _receipt(_login(s2), e2.id)
    assert r2.status_code == 404 and r2.json()["error"]["code"] == "RECEIPT_NOT_AVAILABLE"


def test_has_receipt_signal_correctness(env, s3):
    """has_receipt is a FETCHABLE-receipt signal, NOT payment_status=='paid'."""
    sps, db, mk = env
    s_r, e_r = mk("R", paid=True, receipt=True)             # genuine #6-paid → true
    s_n, e_n = mk("N", paid=True, receipt=False)            # paid, receipt_s3_key null → FALSE (the gap)
    s_o, e_o = mk("O")                                      # unpaid → false

    def has(cli):
        return cli.get("/api/academy/students/me/enrollments", headers=HOST).json()[0]

    r = has(_login(s_r)); n = has(_login(s_n)); o = has(_login(s_o))
    assert r["has_receipt"] is True and r["payment_status"] == "paid"
    assert n["has_receipt"] is False and n["payment_status"] == "paid"   # paid but no fetchable receipt
    assert o["has_receipt"] is False and o["payment_status"] == "pending"


def test_receipt_gate(env, s3):
    sps, db, mk = env
    s, e = mk("A", paid=True, receipt=True)
    assert TestClient(app).get(
        f"/api/academy/students/me/enrollments/{e.id}/receipt", headers=HOST).status_code == 401
    from app.security import create_access_token
    staff = TestClient(app)
    staff.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()),
                      "tenant_id": str(sps.id), "role": "admin"}))
    assert _receipt(staff, e.id).status_code == 401
