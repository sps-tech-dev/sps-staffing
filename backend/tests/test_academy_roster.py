"""FE#8a — admin roster read (staff-gated, tenant+BU-scoped CROSS-student read).
The GATE is load-bearing (not own-scoping): flag-off 404, a student session can't
read the staff roster, a bound CLIENT session is rejected (cross-client leak), and
tenant isolation holds. Staff see ALL in-tenant ACADEMY enrolments, UNMASKED."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Student
from app.security import create_access_token, hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadRost!1234"
STAFF = "roster-staff@local.test"
EP = "/api/academy/enrollments"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []

    # staff user (recruiter is a STAFF_ROLE) on SPS001
    old = db.execute(select(User).where(User.tenant_id == sps.id, User.email == STAFF)).scalar_one_or_none()
    if old:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    staff = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW),
                 full_name="Roster Staff", status="active")
    db.add(staff); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=staff.id, business_unit_id=bu.id, roles=["recruiter"]))

    def enrol(tenant, tag, status="offered"):
        s = Student(tenant_id=tenant.id, business_unit_id="ACADEMY", full_name=f"Roster {tag}",
                    email=f"roster-{tag}-{uuid.uuid4().hex[:6]}@local.test",
                    student_id=f"COLL-{tag}", college_name="Sample College")
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=tenant.id, business_unit_id="ACADEMY", title=f"Roster {tag}",
                   slug=f"roster-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=tenant.id, business_unit_id="ACADEMY", course_id=c.id, name=f"Batch {tag}")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=tenant.id, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status=status,
                       aptitude_score=88, discount_percent=15, final_fee=42500)
        db.add(e); db.flush(); made.append(e)
        return s, c, co, e

    # two SPS001 students (cross-student roster) + a SECOND tenant (isolation)
    sA = enrol(sps, "A", status="offered")
    sB = enrol(sps, "B", status="applied")
    t2 = Tenant(code=f"T2-{uuid.uuid4().hex[:6]}", slug=f"t2{uuid.uuid4().hex[:6]}", name="Iso Tenant")
    db.add(t2); db.flush(); made.append(t2)
    sC = enrol(t2, "C", status="offered")     # T2 enrolment — must NOT appear to SPS001 staff
    db.commit()
    yield sps, db, staff, sA, sB, (t2, sC)
    db.execute(delete(Enrollment).where(Enrollment.id.in_([o.id for o in made if isinstance(o, Enrollment)])))
    for obj in reversed(made):
        if not isinstance(obj, (Enrollment, Tenant)):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.execute(delete(Tenant).where(Tenant.id == t2.id))
    db.execute(delete(Membership).where(Membership.user_id == staff.id))
    db.execute(delete(User).where(User.id == staff.id))
    db.commit(); db.close()


def _staff_client():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": STAFF, "password": PW}, headers=HOST).status_code == 200
    return c


def test_flag_off_404(env, monkeypatch):
    sps, db, *_ = env
    monkeypatch.setattr(settings, "feature_academy", False)
    assert _staff_client().get(EP, headers=HOST).status_code == 404


def test_no_session_and_student_session_rejected(env):
    sps, db, staff, sA, sB, _ = env
    assert TestClient(app).get(EP, headers=HOST).status_code == 401       # no session
    # a STUDENT academy session is NOT a staff session (no access_token → 401)
    sA_student = sA[0]
    sA_student.password_hash = hash_password(PW); db.commit()
    stu = TestClient(app)
    assert stu.post("/api/academy/auth/login", json={"email": sA_student.email, "password": PW},
                    headers=HOST).status_code == 200
    assert stu.get(EP, headers=HOST).status_code == 401                   # student cookie ≠ staff roster


def test_client_portal_session_403(env):
    """The sharpest gate: a bound client-portal session must NOT see the academy
    roster (cross-client leak)."""
    sps, db, *_ = env
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token({
        "sub": str(uuid.uuid4()), "tenant_id": str(sps.id), "role": "client",
        "client_id": str(uuid.uuid4())}))
    assert client.get(EP, headers=HOST).status_code == 403


def test_staff_sees_all_in_tenant_unmasked(env):
    sps, db, staff, sA, sB, _ = env
    rows = _staff_client().get(EP, headers=HOST).json()
    ids = {r["enrollment_id"] for r in rows}
    assert str(sA[3].id) in ids and str(sB[3].id) in ids                  # cross-student = CORRECT
    row = next(r for r in rows if r["enrollment_id"] == str(sA[3].id))
    # UNMASKED identity (the intended staff exposure) — but NO phone/pan
    assert row["student"]["full_name"] == "Roster A" and row["student"]["email"] == sA[0].email
    assert row["student"]["college_name"] == "Sample College"
    assert "phone" not in str(row).lower() and "pan" not in row["student"]


def test_tenant_isolation(env):
    sps, db, staff, sA, sB, iso = env
    t2, sC = iso
    c = _staff_client()
    rows = c.get(EP, headers=HOST).json()
    assert str(sC[3].id) not in {r["enrollment_id"] for r in rows}        # T2 not visible to SPS001 staff
    # a T2 enrolment id via detail → 404 (no existence oracle across the tenant boundary)
    assert c.get(f"{EP}/{sC[3].id}", headers=HOST).status_code == 404


def test_status_filter(env):
    sps, db, staff, sA, sB, _ = env
    c = _staff_client()
    applied = c.get(f"{EP}?status=applied", headers=HOST).json()
    ids = {r["enrollment_id"] for r in applied}
    assert str(sB[3].id) in ids and str(sA[3].id) not in ids              # sB is applied, sA offered


def test_detail_unmasked_plus_payment_and_test(env):
    sps, db, staff, sA, sB, _ = env
    r = _staff_client().get(f"{EP}/{sA[3].id}", headers=HOST)
    assert r.status_code == 200
    d = r.json()
    assert d["student"]["full_name"] == "Roster A" and "course_degree" in d["student"]
    assert "payment" in d and "test" in d                                # detail carries payment + test blocks


def test_student_me_unchanged_own_scoped(env):
    """No regression: the student /me surface stays own-scoped (never cross-student)."""
    sps, db, staff, sA, sB, _ = env
    a = sA[0]; a.password_hash = hash_password(PW); db.commit()
    stu = TestClient(app)
    stu.post("/api/academy/auth/login", json={"email": a.email, "password": PW}, headers=HOST)
    rows = stu.get("/api/academy/students/me/enrollments", headers=HOST).json()
    assert len(rows) == 1 and rows[0]["enrollment_id"] == str(sA[3].id)   # only their OWN
