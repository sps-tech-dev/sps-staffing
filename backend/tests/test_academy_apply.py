"""CREATE-1 — the apply endpoint (first production creator of an 'applied' enrolment)
+ the public applyable-cohorts read. Own-scoping (student_id from the SESSION, never
the body), course-level dedup (one live per course; dropped/cancelled re-appliable),
and double-submit safety (the UNIQUE(cohort,student) race caught as 409) are the
load-bearing properties."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import AuditLog, Tenant
from app.models_academy import Cohort, Course, Enrollment, Student
from app.security import create_access_token, hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "AcadApply!1234"
APPLY_EP = "/api/academy/students/me/enrollments"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    made: list = []

    def course(published=True):
        c = Course(tenant_id=sps.id, business_unit_id="ACADEMY", title="Apply Course",
                   slug=f"apply-{uuid.uuid4().hex[:8]}", fee=50000,
                   is_published=published, status="active" if published else "draft")
        db.add(c); db.flush(); made.append(c)
        return c

    def cohort(c, status="open"):
        co = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=c.id,
                    name=f"Batch {status}", status=status, mode="online")
        db.add(co); db.flush(); made.append(co)
        return co

    pub = course(published=True)
    open_co, planned_co, running_co = cohort(pub, "open"), cohort(pub, "planned"), cohort(pub, "running")
    other = course(published=True); other_co = cohort(other, "open")
    draft = course(published=False); draft_co = cohort(draft, "open")

    s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="Apply Stu",
                email=f"apply-{uuid.uuid4().hex[:6]}@local.test", password_hash=hash_password(PW))
    db.add(s); db.flush(); made.append(s)
    db.commit()
    yield dict(db=db, sps=sps, student=s, pub=pub, open_co=open_co, planned_co=planned_co,
               running_co=running_co, other=other, other_co=other_co, draft=draft, draft_co=draft_co, cohort=cohort)
    ids = list(db.execute(select(Enrollment.id).where(Enrollment.student_id == s.id)).scalars().all())
    db.execute(delete(AuditLog).where(AuditLog.action == "academy.enrolment.apply", AuditLog.entity_id.in_(ids)))
    db.execute(delete(Enrollment).where(Enrollment.student_id == s.id))
    for obj in reversed(made):
        db.execute(delete(type(obj)).where(type(obj).id == obj.id))
    db.commit(); db.close()


def _login(email):
    c = TestClient(app)
    assert c.post("/api/academy/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200
    return c


def _apply(client, course_id, cohort_id, **extra):
    return client.post(APPLY_EP, json={"course_id": str(course_id), "cohort_id": str(cohort_id), **extra}, headers=HOST)


# ── happy + own-scoping ──
def test_apply_happy_and_own_scoped(env):
    db, s = env["db"], env["student"]
    c = _login(s.email)
    # a rogue student_id in the body must be IGNORED — student comes from the session
    r = _apply(c, env["pub"].id, env["open_co"].id, student_id=str(uuid.uuid4()))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "applied" and body["payment_status"] == "pending"
    e = db.get(Enrollment, uuid.UUID(body["enrollment_id"])); db.refresh(e)
    assert e.student_id == s.id                                   # SESSION student, not the body
    assert e.tenant_id == s.tenant_id and e.business_unit_id == "ACADEMY"
    assert e.course_id == env["pub"].id and e.cohort_id == env["open_co"].id
    # everything grade/pay fills is NULL at creation
    assert e.aptitude_score is None and e.discount_percent is None and e.final_fee is None
    assert e.payment_id is None and e.enrolled_at is None


def test_planned_cohort_is_applyable(env):
    db, s = env["db"], env["student"]
    assert _apply(_login(s.email), env["pub"].id, env["planned_co"].id).status_code == 201


# ── course-level dedup + terminal re-apply ──
def test_course_dedup_and_terminal_reapply(env):
    db, s = env["db"], env["student"]
    c = _login(s.email)
    assert _apply(c, env["pub"].id, env["open_co"].id).status_code == 201       # 1st, cohort open
    # 2nd apply to the SAME course, a DIFFERENT cohort → course-level dedup 409
    r2 = _apply(c, env["pub"].id, env["planned_co"].id)
    assert r2.status_code == 409 and r2.json()["error"]["code"] == "ALREADY_APPLIED"
    # drop the live one → re-apply to a NEW cohort succeeds (live excludes terminal)
    live = db.execute(select(Enrollment).where(Enrollment.student_id == s.id, Enrollment.status == "applied")).scalar_one()
    live.status = "dropped"; db.commit()
    fresh = env["cohort"](env["pub"], "open")                                   # a distinct applyable cohort
    db.commit()
    assert _apply(c, env["pub"].id, fresh.id).status_code == 201


def test_same_cohort_double_submit_dedup_and_unique(env):
    db, s = env["db"], env["student"]
    c = _login(s.email)
    assert _apply(c, env["pub"].id, env["open_co"].id).status_code == 201
    # same course+cohort again, prior is LIVE → dedup 409 (before the unique)
    assert _apply(c, env["pub"].id, env["open_co"].id).status_code == 409
    # now the UNIQUE-catch path: a DROPPED prior in this cohort (dedup passes) → insert
    # violates UNIQUE(cohort,student) → caught as 409, NOT a 500
    live = db.execute(select(Enrollment).where(Enrollment.student_id == s.id, Enrollment.cohort_id == env["open_co"].id)).scalar_one()
    live.status = "dropped"; db.commit()
    r = _apply(c, env["pub"].id, env["open_co"].id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_APPLIED"   # unique-catch, not 500


# ── validation ──
def test_validation(env):
    db, s = env["db"], env["student"]
    c = _login(s.email)
    assert _apply(c, env["draft"].id, env["draft_co"].id).status_code == 404        # unpublished course
    assert _apply(c, env["pub"].id, env["other_co"].id).status_code == 422          # cohort of a DIFFERENT course
    assert _apply(c, env["pub"].id, env["running_co"].id).status_code == 422        # closed (running) cohort


# ── gate ──
def test_gate(env):
    db, s = env["db"], env["student"]
    assert _apply(TestClient(app), env["pub"].id, env["open_co"].id).status_code == 401    # no session
    staff = TestClient(app)
    staff.cookies.set("access_token", create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(s.tenant_id), "role_flat": ["recruiter"]}))
    assert _apply(staff, env["pub"].id, env["open_co"].id).status_code == 401             # staff token ≠ student


# ── the public applyable-cohorts read ──
def test_public_cohorts_read(env):
    db = env["db"]
    c = TestClient(app)
    r = c.get(f"/api/academy/public/courses/{env['pub'].slug}/cohorts", headers=HOST)
    assert r.status_code == 200
    payload = r.json()
    assert payload["course_id"] == str(env["pub"].id)                               # course_id carried for apply
    statuses = {row["status"] for row in payload["cohorts"]}
    assert statuses == {"open", "planned"}                                          # NOT running/completed/cancelled
    assert c.get(f"/api/academy/public/courses/{env['draft'].slug}/cohorts", headers=HOST).status_code == 404  # unpublished
    # a published course with no applyable cohorts → empty list (clean, not an error)
    empty = env["cohort"].__self__ if False else None
    from app.models_academy import Course as _C
    lonely = _C(tenant_id=env["sps"].id, business_unit_id="ACADEMY", title="Lonely",
                slug=f"lonely-{uuid.uuid4().hex[:8]}", fee=1, is_published=True, status="active")
    db.add(lonely); db.commit()
    r2 = c.get(f"/api/academy/public/courses/{lonely.slug}/cohorts", headers=HOST)
    assert r2.status_code == 200 and r2.json() == {"course_id": str(lonely.id), "cohorts": []}
    db.execute(delete(_C).where(_C.id == lonely.id)); db.commit()
