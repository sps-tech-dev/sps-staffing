"""8b-3 — STAFF fee-waive. The money-model correctness is the point: a waiver
creates NO Payment row, NO receipt (has_receipt stays correctly false), sets
payment_status='waived', and reaches 'active' through the SAME activation seam as
payment (one entry point). The payment path is unchanged by the seam split."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.academy_deps import StudentContext
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, BusinessUnit, Membership, Notification, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.security import create_access_token, hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadWaive!1234"
STAFF = "waive-staff@local.test"
TRANSITION = "academy.enrollment.transition"
FEE_WAIVED = "academy.enrolment.fee_waived"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []
    old = db.execute(select(User).where(User.tenant_id == sps.id, User.email == STAFF)).scalar_one_or_none()
    if old:
        db.execute(delete(Membership).where(Membership.user_id == old.id)); db.execute(delete(User).where(User.id == old.id))
    staff = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW), full_name="Waive Staff", status="active")
    db.add(staff); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=staff.id, business_unit_id=bu.id, roles=["recruiter"]))

    def enrol(tenant, status="offered"):
        s = Student(tenant_id=tenant.id, business_unit_id="ACADEMY", full_name="Waive Stu",
                    email=f"waive-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=tenant.id, business_unit_id="ACADEMY", title="Waive", slug=f"waive-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=tenant.id, business_unit_id="ACADEMY", course_id=c.id, name="B")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=tenant.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status=status, aptitude_score=70, discount_percent=0, final_fee=50000)
        db.add(e); db.flush(); made.append(e); db.commit()
        return s, e

    t2 = Tenant(code=f"T2-{uuid.uuid4().hex[:6]}", slug=f"t2{uuid.uuid4().hex[:6]}", name="Iso")
    db.add(t2); db.flush(); made.append(t2)
    db.commit()
    yield sps, db, staff, enrol, t2
    ids = [o.id for o in made if isinstance(o, Enrollment)]
    db.execute(delete(AuditLog).where(AuditLog.action.in_([TRANSITION, FEE_WAIVED]), AuditLog.entity_id.in_(ids)))
    db.execute(delete(Notification).where(Notification.idempotency_key.in_([f"academy:fee_waived:{i}" for i in ids])))
    db.execute(delete(Payment).where(Payment.enrollment_id.in_(ids)))
    for obj in reversed(made):
        if not isinstance(obj, Tenant):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.execute(delete(Tenant).where(Tenant.id == t2.id))
    db.execute(delete(Membership).where(Membership.user_id == staff.id))
    db.execute(delete(User).where(User.id == staff.id))
    db.commit(); db.close()


def _staff():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": STAFF, "password": PW}, headers=HOST).status_code == 200
    return c


def _waive(client, enr_id, reason=None):
    body = {} if reason is None else {"reason": reason}
    return client.post(f"/api/academy/enrollments/{enr_id}/waive", json=body, headers=HOST)


def _audits(db, enr_id, action):
    return db.execute(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == enr_id)).scalars().all()


# ── the money model: waiver = activation WITHOUT money ──
def test_waiver_happy_no_payment_no_receipt(env):
    sps, db, staff, enrol, _ = env
    s, e = enrol(sps, "offered")
    r = _waive(_staff(), e.id, reason="Scholarship — merit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active" and body["payment_status"] == "waived"
    db.refresh(e)
    assert e.status == "active" and e.payment_status == "waived" and e.payment_id is None
    # NO Payment row exists for a waiver
    assert db.execute(select(Payment).where(Payment.enrollment_id == e.id)).scalars().all() == []
    # audits: the transition (offered→active, system) AND a distinct fee_waived (staff actor + reason)
    ta = _audits(db, e.id, TRANSITION)
    assert len(ta) == 1 and ta[0].after["from"] == "offered" and ta[0].after["to"] == "active" and ta[0].after["kind"] == "system"
    fw = _audits(db, e.id, FEE_WAIVED)
    assert len(fw) == 1 and fw[0].after["reason"] == "Scholarship — merit" and fw[0].after["actor"] == str(staff.id) and fw[0].actor_id == staff.id
    # the WAIVER email (not the payment email)
    n = db.execute(select(Notification).where(Notification.idempotency_key == f"academy:fee_waived:{e.id}")).scalar_one()
    assert n.template_code == "academy_enrolment_waived" and n.recipient == s.email
    assert db.execute(select(Notification).where(Notification.template_code == "academy_enrolment_active",
            Notification.recipient == s.email)).first() is None      # NOT the payment email


def test_has_receipt_false_and_receipt_endpoint_404(env):
    """Coherent: a waiver has genuinely no receipt — has_receipt false, download 404s."""
    sps, db, staff, enrol, _ = env
    s, e = enrol(sps, "offered")
    _waive(_staff(), e.id, reason="Waived")
    # has_receipt is derived from a paid Payment WITH a receipt_s3_key — there is none
    assert db.execute(select(Payment).where(Payment.enrollment_id == e.id, Payment.status == "paid",
            Payment.receipt_s3_key.isnot(None))).first() is None
    from app.routers.academy import student_receipt
    with pytest.raises(HTTPException) as ei:
        student_receipt(enrollment_id=e.id,
                        student=StudentContext(student_id=s.id, tenant_id=str(sps.id), email=s.email, college_student_id=None),
                        db=db)
    assert ei.value.status_code == 404 and ei.value.detail["code"] == "RECEIPT_NOT_AVAILABLE"


# ── the staff gate (reuse 8a/8b-2 cases) ──
def test_gate(env, monkeypatch):
    sps, db, staff, enrol, _ = env
    s, e = enrol(sps, "offered")
    assert _waive(TestClient(app), e.id, "x").status_code == 401                    # no session
    cli = TestClient(app)
    cli.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(sps.id),
                    "role_flat": ["client"], "client_id": str(uuid.uuid4())}))
    assert _waive(cli, e.id, "x").status_code == 403                                # bound client
    stu = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="S",
                  email=f"w-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
    db.add(stu); db.commit()
    sc = TestClient(app)
    sc.post("/api/academy/auth/login", json={"email": stu.email, "password": PW}, headers=HOST)
    assert _waive(sc, e.id, "x").status_code == 401                                 # student ≠ staff
    db.execute(delete(Student).where(Student.id == stu.id)); db.commit()
    monkeypatch.setattr(settings, "feature_academy", False)
    assert _waive(_staff(), e.id, "x").status_code == 404                           # flag off


def test_tenant_isolation(env):
    sps, db, staff, enrol, t2 = env
    s, e2 = enrol(t2, "offered")
    assert _waive(_staff(), e2.id, "x").status_code == 404                          # T1 staff, T2 enrolment
    db.refresh(e2); assert e2.status == "offered" and e2.payment_status != "waived"


# ── preconditions ──
def test_preconditions(env):
    sps, db, staff, enrol, _ = env
    c = _staff()
    # missing reason → 422
    r = _waive(c, enrol(sps, "offered")[1].id, reason=None)
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    # not-offered → 409 (applied, tested, active)
    for st in ("applied", "tested", "active"):
        assert _waive(c, enrol(sps, st)[1].id, "x").status_code == 409
    # double-waive → 409 (already active after the first waive)
    _, e = enrol(sps, "offered")
    assert _waive(c, e.id, "first").status_code == 200
    assert _waive(c, e.id, "second").status_code == 409                             # no double-waive
