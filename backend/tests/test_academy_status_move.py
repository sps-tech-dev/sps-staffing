"""8b-2 — STAFF manual status move. Risk is the STAFF GATE + tenant/BU scope (like
8a) and that the endpoint DELEGATES legality to the 8b-1 machine (no duplicated
rules). The dangerous move (→active) is machine-forbidden to manual callers — the
endpoint must surface that 409, not separately block or allow it."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, BusinessUnit, Membership, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Student
from app.security import create_access_token, hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadMove!1234"
STAFF = "move-staff@local.test"
TRANSITION = "academy.enrollment.transition"


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
    staff = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW), full_name="Move Staff", status="active")
    db.add(staff); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=staff.id, business_unit_id=bu.id, roles=["recruiter"]))

    def enrol(tenant, status="offered"):
        s = Student(tenant_id=tenant.id, business_unit_id="ACADEMY", full_name="Move Stu",
                    email=f"move-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=tenant.id, business_unit_id="ACADEMY", title="Move", slug=f"move-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=tenant.id, business_unit_id="ACADEMY", course_id=c.id, name="B")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=tenant.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status=status)
        db.add(e); db.flush(); made.append(e)
        db.commit()          # commit so the endpoint's fresh session sees it
        return e

    t2 = Tenant(code=f"T2-{uuid.uuid4().hex[:6]}", slug=f"t2{uuid.uuid4().hex[:6]}", name="Iso")
    db.add(t2); db.flush(); made.append(t2)
    db.commit()
    yield sps, db, staff, enrol, t2
    ids = [o.id for o in made if isinstance(o, Enrollment)]
    db.execute(delete(AuditLog).where(AuditLog.action == TRANSITION, AuditLog.entity_id.in_(ids)))
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


def _move(client, enr_id, to_state, reason=None):
    body = {"to_state": to_state}
    if reason is not None:
        body["reason"] = reason
    return client.post(f"/api/academy/enrollments/{enr_id}/status", json=body, headers=HOST)


def _last_audit(db, enr_id):
    return db.execute(select(AuditLog).where(AuditLog.action == TRANSITION, AuditLog.entity_id == enr_id)
                      .order_by(AuditLog.id.desc())).scalars().first()


# ── the staff gate (reuse 8a's cases) ──
def test_flag_off_404(env, monkeypatch):
    sps, db, staff, enrol, _ = env
    e = enrol(sps)
    monkeypatch.setattr(settings, "feature_academy", False)
    assert _move(_staff(), e.id, "cancelled", "x").status_code == 404


def test_no_session_and_student_and_client_gate(env):
    sps, db, staff, enrol, _ = env
    e = enrol(sps)
    assert _move(TestClient(app), e.id, "cancelled", "x").status_code == 401       # no session
    stu = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="S",
                  email=f"m-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
    db.add(stu); db.commit()
    sc = TestClient(app)
    sc.post("/api/academy/auth/login", json={"email": stu.email, "password": PW}, headers=HOST)
    assert _move(sc, e.id, "cancelled", "x").status_code == 401                     # student ≠ staff
    db.execute(delete(Student).where(Student.id == stu.id)); db.commit()
    cli = TestClient(app)
    cli.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(sps.id),
                    "role_flat": ["client"], "client_id": str(uuid.uuid4())}))
    assert _move(cli, e.id, "cancelled", "x").status_code == 403                    # bound client


def test_tenant_isolation(env):
    sps, db, staff, enrol, t2 = env
    e2 = enrol(t2, status="offered")
    assert _move(_staff(), e2.id, "cancelled", "x").status_code == 404             # T1 staff, T2 enrolment → 404
    db.refresh(e2); assert e2.status == "offered"                                  # untouched


# ── happy manual moves + actor-is-staff ──
def test_manual_moves_happy_with_staff_actor(env):
    sps, db, staff, enrol, _ = env
    c = _staff()
    for start, to in [("offered", "cancelled"), ("active", "dropped"), ("active", "completed")]:
        e = enrol(sps, status=start)
        r = _move(c, e.id, to, reason=f"admin: {to}")
        assert r.status_code == 200 and r.json()["status"] == to, r.text
        db.refresh(e); assert e.status == to
        a = _last_audit(db, e.id)
        assert a.after["kind"] == "manual" and a.after["reason"] == f"admin: {to}"
        assert a.after["actor"] == str(staff.id) and a.actor_id == staff.id       # attributable to the STAFF user


# ── delegation to the machine (not re-implemented) ──
def test_delegates_all_rejections_to_machine(env):
    sps, db, staff, enrol, _ = env
    c = _staff()
    # manual → active is machine-forbidden (system edge) — surfaces as 409, endpoint didn't block it
    assert _move(c, enrol(sps, "offered").id, "active", "force").status_code == 409
    # from terminal
    assert _move(c, enrol(sps, "cancelled").id, "offered", "x").status_code == 409
    # not in table (backwards)
    assert _move(c, enrol(sps, "active").id, "applied", "x").status_code == 409
    # missing reason → machine 422
    r = _move(c, enrol(sps, "offered").id, "cancelled", reason=None)
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    # garbage to_state → endpoint 422 (validation before the machine)
    r2 = _move(c, enrol(sps, "offered").id, "banana", "x")
    assert r2.status_code == 422 and r2.json()["error"]["code"] == "VALIDATION_ERROR"
