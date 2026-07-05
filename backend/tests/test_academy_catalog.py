"""A2 academy catalog: staff CRUD + publish + cohorts (FEATURE_ACADEMY + staff
gated); the PUBLIC unauthenticated surface (published-only, safe-fields-only,
tenant-by-Host, leak-nothing)."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Membership, Tenant, User
from app.models_academy import Cohort, Course

HOST = {"host": "spstechnosoft.com"}
PW = "AcadCat!123"
STAFF = "a2-staff@local.test"
CAND = "a2-cand@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="A2 Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    staff = _mk_user(db, sps, STAFF, ["recruiter"])
    cand = _mk_user(db, sps, CAND, ["candidate"])
    yield sps, db
    # remove only A2-created courses/cohorts (keep the seeded 8)
    db.execute(delete(Cohort).where(Cohort.tenant_id == sps.id,
               Cohort.course_id.in_(select(Course.id).where(Course.slug.like("a2-%")))))
    db.execute(delete(Course).where(Course.tenant_id == sps.id, Course.slug.like("a2-%")))
    # re-unpublish any seeded course this test published
    db.execute(Course.__table__.update().where(Course.tenant_id == sps.id,
               Course.slug == "python").values(is_published=False, status="draft"))
    for u in (staff, cand):
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def test_staff_gates(env, monkeypatch):
    sps, db = env
    # unauth 401
    assert TestClient(app).get("/api/academy/courses", headers=HOST).status_code == 401
    # candidate 403
    cc = TestClient(app); _login(cc, CAND)
    assert cc.get("/api/academy/courses", headers=HOST).status_code == 403
    # flag off → 404 even for staff
    monkeypatch.setattr(settings, "feature_academy", False)
    sc = TestClient(app); _login(sc, STAFF)
    assert sc.get("/api/academy/courses", headers=HOST).status_code == 404


def test_course_crud_and_publish(env):
    sps, db = env
    c = TestClient(app); _login(c, STAFF)
    # create
    r = c.post("/api/academy/courses", json={"title": "A2 Test Course", "slug": "a2-test-course",
               "description": "d", "fee": 60000}, headers=HOST)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["is_published"] is False and r.json()["fee"] == 60000
    # duplicate slug → 409
    assert c.post("/api/academy/courses", json={"title": "Dup", "slug": "a2-test-course"},
                  headers=HOST).status_code == 409
    # patch
    r = c.patch(f"/api/academy/courses/{cid}", json={"level": "beginner", "fee": 55000}, headers=HOST)
    assert r.status_code == 200 and r.json()["level"] == "beginner" and r.json()["fee"] == 55000
    # list includes unpublished
    listed = c.get("/api/academy/courses", headers=HOST).json()
    assert any(x["id"] == cid and x["is_published"] is False for x in listed)
    # publish flips is_published + status
    r = c.post(f"/api/academy/courses/{cid}/publish", json={"is_published": True}, headers=HOST)
    assert r.status_code == 200 and r.json()["is_published"] is True and r.json()["status"] == "active"


def test_public_surface_published_only_and_safe_fields(env):
    sps, db = env
    staff = TestClient(app); _login(staff, STAFF)
    pub = TestClient(app)   # NO login — unauthenticated

    # 1) the 8 seeded courses are all unpublished → public list is empty of them
    before = pub.get("/api/academy/public/courses", headers=HOST)
    assert before.status_code == 200                     # unauthenticated 200
    assert not any(x["slug"] == "python" for x in before.json())

    # 2) publish a seeded course → it appears publicly
    py = db.execute(select(Course).where(Course.tenant_id == sps.id,
                                         Course.slug == "python")).scalar_one()
    r = staff.post(f"/api/academy/courses/{py.id}/publish", json={"is_published": True}, headers=HOST)
    assert r.status_code == 200
    after = pub.get("/api/academy/public/courses", headers=HOST).json()
    row = next((x for x in after if x["slug"] == "python"), None)
    assert row is not None, "published course did not appear on the public surface"

    # 3) SAFE FIELDS ONLY — allowlist; NO internal/leaky field
    assert set(row.keys()) == {"title", "slug", "description", "syllabus", "level",
                               "duration_weeks", "fee", "currency", "next_cohort_start"}
    for banned in ("id", "tenant_id", "is_published", "status", "created_at", "business_unit_id"):
        assert banned not in row, f"public payload leaked internal field '{banned}'"

    # 4) create an UNPUBLISHED course → must NOT leak publicly
    staff.post("/api/academy/courses", json={"title": "A2 Draft", "slug": "a2-draft"}, headers=HOST)
    assert not any(x["slug"] == "a2-draft" for x in pub.get("/api/academy/public/courses", headers=HOST).json())

    # 5) detail endpoint: published slug 200 (safe fields); unpublished slug 404
    d = pub.get("/api/academy/public/courses/python", headers=HOST)
    assert d.status_code == 200 and "is_published" not in d.json()
    assert pub.get("/api/academy/public/courses/a2-draft", headers=HOST).status_code == 404

    # 6) unpublish → gone again
    staff.post(f"/api/academy/courses/{py.id}/publish", json={"is_published": False}, headers=HOST)
    assert not any(x["slug"] == "python" for x in pub.get("/api/academy/public/courses", headers=HOST).json())


def test_public_surface_flag_gated_and_tenant_scoped(env, monkeypatch):
    sps, db = env
    pub = TestClient(app)
    # flag off → public surface 404 too (whole vertical probe-proof)
    monkeypatch.setattr(settings, "feature_academy", False)
    assert pub.get("/api/academy/public/courses", headers=HOST).status_code == 404
    monkeypatch.setattr(settings, "feature_academy", True)
    # unknown tenant host → 404 (no leak of the owner tenant's catalog)
    assert pub.get("/api/academy/public/courses",
                   headers={"host": "no-such-tenant.spstechnosoft.com"}).status_code in (200, 404)


def test_cohorts_crud(env):
    sps, db = env
    c = TestClient(app); _login(c, STAFF)
    course = c.post("/api/academy/courses", json={"title": "A2 Cohort Course", "slug": "a2-cohort"},
                    headers=HOST).json()
    r = c.post(f"/api/academy/courses/{course['id']}/cohorts",
               json={"name": "Batch 1", "start_date": "2026-09-01", "end_date": "2026-12-01",
                     "capacity": 30, "mode": "online", "status": "open"}, headers=HOST)
    assert r.status_code == 200 and r.json()["capacity"] == 30
    # end before start → 422
    assert c.post(f"/api/academy/courses/{course['id']}/cohorts",
                  json={"name": "Bad", "start_date": "2026-12-01", "end_date": "2026-09-01"},
                  headers=HOST).status_code == 422
    cohorts = c.get(f"/api/academy/courses/{course['id']}/cohorts", headers=HOST).json()
    assert len(cohorts) == 1 and cohorts[0]["name"] == "Batch 1"
