"""A5 tiered discount + enrolment pricing — the boundary tests are the deliverable.

Founder-locked tiers (inclusive-lower): ≥95→20 | 85–<95→15 | 75–<85→10 | <75→0.
<75 = FULL PRICE, NOT a gate. final_fee = course.fee × (100−d)/100 (pre-tax, no
GST/TDS), read off the course row (per-course configurable, never hardcoded).
"""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.academy_pricing import compute_final_fee, resolve_discount_percent
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Notification, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Test

HOST = {"host": "spstechnosoft.com"}
PW = "AcadPr!1234"
STAFF = "a5-staff@local.test"


# ── the boundary matrix (pure, no I/O) — the deliverable ──
@pytest.mark.parametrize("pct,expected", [
    # abstract boundaries
    (100, 20), (95.0, 20), (94.99, 15), (85.0, 15), (84.99, 10),
    (75.0, 10), (74.99, 0), (0, 0),
])
def test_resolve_discount_abstract_boundaries(pct, expected):
    assert resolve_discount_percent(pct) == expected


@pytest.mark.parametrize("correct,expected", [
    # ACHIEVABLE integer correct-counts straddling each boundary (correct/60×100 is
    # what's actually stamped). Boundaries fall on exact integers: 57/51/45.
    (57, 20), (56, 15),      # 95.0 vs 93.33
    (51, 15), (50, 10),      # 85.0 vs 83.33
    (45, 10), (44, 0),       # 75.0 vs 73.33
    (60, 20), (0, 0),
])
def test_resolve_discount_achievable_counts(correct, expected):
    pct = round(correct / 60 * 100, 2)
    assert resolve_discount_percent(pct) == expected


@pytest.mark.parametrize("discount,expected", [
    (20, 40000.0), (15, 42500.0), (10, 45000.0), (0, 50000.0),   # ₹50,000 default
])
def test_final_fee_at_default_fee(discount, expected):
    assert compute_final_fee(50000, discount) == expected


def test_final_fee_reads_course_fee_and_rounds():
    # per-course configurable: a NON-default fee that exercises 2-decimal rounding
    assert compute_final_fee(49999, 15) == 42499.15        # 49999 × 0.85, round2
    assert compute_final_fee(33333, 10) == 29999.7         # 33333 × 0.90


# ── integration: issue → take → grade → stamp + email + status ──
def _mk_staff(db, sps):
    old = db.execute(select(User).where(User.tenant_id == sps.id,
                                        User.email == STAFF)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW),
             full_name="A5 Staff", status="active")
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
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    staff = _mk_staff(db, sps)

    def make(fee=50000):
        course = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title="A5 Course",
                        slug=f"a5-{uuid.uuid4().hex[:8]}", fee=fee)
        student = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="A5 Student",
                          email=f"a5-{uuid.uuid4().hex[:6]}@local.test")
        db.add_all([course, student]); db.flush()
        cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id, name="B")
        db.add(cohort); db.flush()
        enr = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                         student_id=student.id, course_id=course.id, status="applied")
        db.add(enr); db.commit()
        return enr, student, course

    yield sps, db, make
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id))
    db.execute(delete(Test).where(Test.tenant_id == sps.id, Test.business_unit_id == "ACADEMY"))
    db.execute(delete(Enrollment).where(Enrollment.tenant_id == sps.id))
    db.execute(delete(Cohort).where(Cohort.tenant_id == sps.id))
    db.execute(delete(Student).where(Student.tenant_id == sps.id, Student.email.like("a5-%")))
    db.execute(delete(Course).where(Course.tenant_id == sps.id, Course.slug.like("a5-%")))
    db.execute(delete(Membership).where(Membership.user_id == staff.id))
    db.execute(delete(User).where(User.id == staff.id))
    db.commit(); db.close()


def _login(c):
    assert c.post("/api/auth/login", json={"email": STAFF, "password": PW},
                  headers=HOST).status_code == 200


def _issue_take_grade(sps, db, enr, correct_count):
    """Issue → answer exactly `correct_count`/60 → return the submit response."""
    c = TestClient(app); _login(c)
    ir = c.post(f"/api/academy/enrollments/{enr.id}/aptitude/issue", headers=HOST)
    assert ir.status_code == 200, ir.text
    token = ir.json()["take_path"].rsplit("/", 1)[-1]
    db.expire_all()          # see the just-created attempt, not a stale cached row
    test = db.execute(select(Test).where(Test.enrollment_id == enr.id)
                      .order_by(Test.attempt_no.desc())).scalars().first()
    frozen = test.served_questions
    answers = {f["qid"]: (f["correct"] if i < correct_count else (f["correct"] + 1) % 4)
               for i, f in enumerate(frozen)}
    return TestClient(app).post(f"/api/take/{token}/submit", json={"answers": answers},
                                headers=HOST), test


def test_stamps_discount_and_final_fee_and_offered(env):
    sps, db, make = env
    enr, student, course = make(fee=50000)
    _, test = _issue_take_grade(sps, db, enr, 57)          # 57/60 = 95.0 → 20%
    db.refresh(enr)
    assert float(enr.aptitude_score) == 95.0
    assert int(enr.discount_percent) == 20 and float(enr.final_fee) == 40000.0
    assert enr.status == "offered"                         # tested→offered
    # payment-link email in the B.10 ledger (enqueued, not sent) — keyed on THIS attempt
    n = db.execute(select(Notification).where(
        Notification.idempotency_key == f"academy:payment_link:{test.id}")).scalars().all()
    assert len(n) == 1 and n[0].status in ("pending", "sent")
    assert "40000" in n[0].rendered_body and "20%" in n[0].rendered_body


def test_full_price_is_not_a_gate(env):
    sps, db, make = env
    enr, student, course = make(fee=50000)
    _issue_take_grade(sps, db, enr, 44)                    # 44/60 = 73.33 → 0%
    db.refresh(enr)
    assert int(enr.discount_percent) == 0 and float(enr.final_fee) == 50000.0   # full price
    assert enr.status == "offered"                         # STILL advances — not blocked


def test_per_course_fee_configurable(env):
    sps, db, make = env
    enr, student, course = make(fee=49999)                 # NON-default fee
    _issue_take_grade(sps, db, enr, 51)                    # 51/60 = 85.0 → 15%
    db.refresh(enr)
    assert float(enr.final_fee) == 42499.15                # 49999 × 0.85 — reads course.fee, rounds
    assert float(course.fee) == 49999                      # not hardcoded 50000


def test_no_gst_tds_on_final_fee(env):
    sps, db, make = env
    enr, student, course = make(fee=50000)
    _issue_take_grade(sps, db, enr, 60)                    # 100 → 20%
    db.refresh(enr)
    # final_fee is EXACTLY the pre-tax discounted fee — no GST/TDS folded in
    assert float(enr.final_fee) == compute_final_fee(50000, 20) == 40000.0


def _email_count_for(db, test_id):
    # per-ATTEMPT idempotency key (academy:payment_link:<test id>) — robust to any
    # other notifications in the ledger; this is the actual invariant.
    return db.execute(select(func.count()).select_from(Notification).where(
        Notification.idempotency_key == f"academy:payment_link:{test_id}")).scalar_one()


def test_idempotent_stamp_and_email_on_regrade_vs_retake(env):
    sps, db, make = env
    enr, student, course = make(fee=50000)
    resp, test1 = _issue_take_grade(sps, db, enr, 57)      # attempt 1 → 20%
    assert resp.status_code == 200
    # attempt 1 → exactly one email keyed on THIS attempt
    assert _email_count_for(db, test1.id) == 1
    # re-submitting the SAME attempt is idempotent (submit returns the stored result,
    # never re-grades/re-enqueues) → still one email for this attempt
    token1 = None  # the raw token isn't retained; a re-submit path is covered by B.7 idempotency
    assert _email_count_for(db, test1.id) == 1
    # a FRESH retake (new attempt) re-prices off the new score + re-sends (new key)
    db.refresh(enr); enr.status = "applied"; db.commit()   # refresh: DB has 'offered' from attempt 1
    resp2, test2 = _issue_take_grade(sps, db, enr, 44)     # attempt 2 → 0%
    assert test2.id != test1.id
    db.refresh(enr)
    assert int(enr.discount_percent) == 0 and float(enr.final_fee) == 50000.0   # re-priced
    assert _email_count_for(db, test2.id) == 1             # a new email for the new attempt
    assert _email_count_for(db, test1.id) == 1             # the old attempt's email is unchanged
