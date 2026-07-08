"""8b-1 — the enrolment transition machine + the two writers routed through it.
The machine is the single authority: illegal moves fail closed, a manual caller
can never reach a [system] target ('active'), terminal states are dead ends, and
every successful move emits an academy.enrollment.transition audit (silent before)."""
from __future__ import annotations

import uuid

import boto3
import pytest
from fastapi import HTTPException
from moto import mock_aws
from sqlalchemy import delete, func, select

from app.academy_deps import StudentContext
from app.academy_transitions import transition
from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import AuditLog, Tenant
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.models_staffing import Test

TRANSITION_ACTION = "academy.enrollment.transition"


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

    def mk(status="applied", **kw):
        s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="T8b1",
                    email=f"t8b1-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title="T8b1",
                   slug=f"t8b1-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=c.id, name="B")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status=status, **kw)
        db.add(e); db.flush(); made.append(e)
        db.commit()
        return s, e

    yield sps, db, mk
    ids = [o.id for o in made if isinstance(o, Enrollment)]
    db.execute(delete(AuditLog).where(AuditLog.action == TRANSITION_ACTION, AuditLog.entity_id.in_(ids)))
    db.execute(delete(Payment).where(Payment.enrollment_id.in_(ids)))
    db.execute(delete(Test).where(Test.enrollment_id.in_(ids)))
    for obj in reversed(made):
        db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _audits(db, enr_id):
    return db.execute(select(AuditLog).where(
        AuditLog.action == TRANSITION_ACTION, AuditLog.entity_id == enr_id)).scalars().all()


# ── the machine: rejections (fail closed) ──
def test_reject_system_edge_from_manual_caller(env):
    """A manual caller can NEVER reach 'active' (offered→active is system-only)."""
    sps, db, mk = env
    _, e = mk("offered")
    with pytest.raises(HTTPException) as ei:
        transition(db, e, "active", kind="manual", reason="admin wants to")
    assert ei.value.status_code == 409 and ei.value.detail["code"] == "ILLEGAL_TRANSITION"
    db.refresh(e); assert e.status == "offered" and len(_audits(db, e.id)) == 0   # nothing happened


def test_reject_from_terminal(env):
    sps, db, mk = env
    _, e = mk("cancelled")
    with pytest.raises(HTTPException) as ei:
        transition(db, e, "offered", kind="system")
    assert ei.value.status_code == 409 and "terminal" in ei.value.detail["message"]


def test_reject_not_in_table(env):
    sps, db, mk = env
    _, e = mk("active")
    with pytest.raises(HTTPException) as ei:      # active→applied is backwards, not in the table
        transition(db, e, "applied", kind="system")
    assert ei.value.status_code == 409 and ei.value.detail["code"] == "ILLEGAL_TRANSITION"


def test_applied_to_tested_forbidden(env):
    """applied→tested is DELIBERATELY absent (no writer performs it — dead vocabulary)."""
    sps, db, mk = env
    _, e = mk("applied")
    with pytest.raises(HTTPException) as ei:
        transition(db, e, "tested", kind="system")
    assert ei.value.status_code == 409 and ei.value.detail["code"] == "ILLEGAL_TRANSITION"


def test_manual_requires_reason(env):
    sps, db, mk = env
    _, e = mk("offered")
    with pytest.raises(HTTPException) as ei:
        transition(db, e, "cancelled", kind="manual", reason=None)
    assert ei.value.status_code == 422 and ei.value.detail["code"] == "REASON_REQUIRED"
    # with a reason → ok + status set + audit row
    transition(db, e, "cancelled", kind="manual", reason="Withdrew", actor="staff-x"); db.commit()
    db.refresh(e); assert e.status == "cancelled"
    a = _audits(db, e.id); assert len(a) == 1 and a[0].after["reason"] == "Withdrew" and a[0].after["kind"] == "manual"


def test_system_happy_sets_status_and_audits(env):
    sps, db, mk = env
    _, e = mk("applied")
    transition(db, e, "offered", kind="system", reason="aptitude_graded", actor="aptitude_engine"); db.commit()
    db.refresh(e); assert e.status == "offered"
    a = _audits(db, e.id)
    assert len(a) == 1 and a[0].after["from"] == "applied" and a[0].after["to"] == "offered" and a[0].after["kind"] == "system"


# ── the two writers now route through + are audited (finding #6 closed) ──
def _staff():
    return RequestContext(tenant_id=None, business_unit_id="ACADEMY", user_id=None, roles=("recruiter",))


def test_grade_routes_through_and_audits(env):
    sps, db, mk = env
    _, e = mk("applied")
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="ACADEMY", user_id=None, roles=("recruiter",))
    from app.routers.academy import issue_aptitude
    from app.routers.take import fetch_paper, submit_answers, SubmitIn
    res = issue_aptitude(enrollment_id=e.id, ctx=ctx, db=db, idempotency_key=None)
    tok = res["take_path"].rsplit("/", 1)[-1]
    t = db.execute(select(Test).where(Test.enrollment_id == e.id)).scalar_one()
    fetch_paper(token=tok, db=db)
    submit_answers(token=tok, body=SubmitIn(answers={f["qid"]: f["correct"] for f in t.served_questions}), db=db)
    db.refresh(e)
    assert e.status == "offered"                                   # behaviour unchanged
    a = _audits(db, e.id)
    assert len(a) == 1 and a[0].after["to"] == "offered" and a[0].after["actor"] == "aptitude_engine"  # NOW audited


def test_pay_routes_through_and_audits(env, s3):
    sps, db, mk = env
    s, e = mk("offered", aptitude_score=96, discount_percent=20, final_fee=40000)
    from app.routers.academy import student_pay
    ctx = StudentContext(student_id=s.id, tenant_id=str(sps.id), email=s.email, college_student_id=None)
    student_pay(enrollment_id=e.id, student=ctx, db=db)
    db.refresh(e)
    assert e.status == "active" and e.payment_status == "paid"     # behaviour unchanged
    a = _audits(db, e.id)
    assert len(a) == 1 and a[0].after["from"] == "offered" and a[0].after["to"] == "active" and a[0].after["actor"] == "payment"
