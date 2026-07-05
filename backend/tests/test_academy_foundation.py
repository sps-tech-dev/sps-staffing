"""A1 academy foundation: the FEATURE_ACADEMY 404-gate, the schema tables +
student PII/linkage columns, and the reproducible 8-course seed."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

from app.academy_seed import SEED_COURSES, seed_courses
from app.config import settings
from app.crypto import EncryptedStr, blind_index, encrypt
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_academy import Course, Student

HOST = {"host": "spstechnosoft.com"}
PW = "AcadLocal!123"
STAFF = "acad-staff@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Acad Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    staff = _mk_user(db, sps, STAFF, ["recruiter"])
    yield sps, db
    db.execute(delete(Student).where(Student.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == staff.id))
    db.execute(delete(User).where(User.id == staff.id))
    db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=HOST).status_code == 200


def test_feature_academy_gates_404_when_off(env, monkeypatch):
    c = TestClient(app); _login(c, STAFF)
    monkeypatch.setattr(settings, "feature_academy", False)
    assert c.get("/api/academy/ping", headers=HOST).status_code == 404
    monkeypatch.setattr(settings, "feature_academy", True)
    r = c.get("/api/academy/ping", headers=HOST)
    assert r.status_code == 200 and r.json()["vertical"] == "academy"


def test_academy_tables_present(env):
    sps, db = env
    tables = db.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'academy'"
    )).scalars().all()
    expected = {"courses", "cohorts", "students", "enrollments", "attendance",
                "assignments", "assignment_submissions", "certificates", "payments"}
    assert expected.issubset(set(tables)), f"missing academy tables: {expected - set(tables)}"


def test_students_pii_columns_and_linkage(env):
    sps, db = env
    # column shapes: user_id present + indexed; phone bidx + email unique
    cols = {r[0]: r[1] for r in db.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='academy' AND table_name='students'")).all()}
    assert cols.get("user_id") == "uuid"                      # F3a soft-ref column
    assert cols.get("phone_enc") == "bytea" and cols.get("phone_bidx") == "bytea"
    assert cols.get("email") == "USER-DEFINED"                # citext
    idx = db.execute(text(
        "SELECT indexname FROM pg_indexes WHERE schemaname='academy' AND tablename='students'"
    )).scalars().all()
    assert "ix_students_user_id" in idx
    # the EncryptedStr type round-trips PII (same treatment as candidates)
    assert isinstance(Student.__table__.c.phone_enc.type, EncryptedStr)
    st = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="PII Student",
                 email="pii-student@local.test", phone_enc="+919812340000",
                 phone_bidx=blind_index("+919812340000"), user_id=None)
    db.add(st); db.commit()
    raw = db.execute(text("SELECT phone_enc FROM academy.students WHERE id=:i"),
                     {"i": str(st.id)}).scalar_one()
    assert b"+919812340000" not in bytes(raw)                 # stored ciphertext, not plaintext
    db.expire(st)
    assert st.phone_enc == "+919812340000"                    # decrypts on access


def test_soft_ref_no_fk_on_user_id(env):
    sps, db = env
    # students.user_id must NOT have a cross-schema FK (soft-ref convention)
    fks = db.execute(text(
        "SELECT con.conname FROM pg_constraint con "
        "JOIN pg_class rel ON rel.oid = con.conrelid "
        "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
        "WHERE ns.nspname='academy' AND rel.relname='students' AND con.contype='f'"
    )).scalars().all()
    joined = " ".join(fks)
    assert "user_id" not in joined, f"user_id should be a soft-ref (no FK); found {fks}"


def test_eight_courses_seed_reproducibly(env):
    sps, db = env
    # the migration seeded them; assert exactly the 8 canonical slugs exist
    rows = db.execute(select(Course).where(Course.tenant_id == sps.id,
                                           Course.deleted_at.is_(None))).scalars().all()
    slugs = {c.slug for c in rows}
    assert {c["slug"] for c in SEED_COURSES}.issubset(slugs)
    assert len(SEED_COURSES) == 8
    seeded = [c for c in rows if c.slug in {s["slug"] for s in SEED_COURSES}]
    assert all(float(c.fee) == 50000 for c in seeded)         # default ₹50,000 (decision 6)
    assert all(c.is_published is False for c in seeded)       # A2 publishes
    assert all(c.currency == "INR" for c in seeded)
    # reproducible + idempotent: re-seeding from empty yields exactly 8, no dupes
    db.execute(delete(Course).where(Course.tenant_id == sps.id))
    db.commit()
    n1 = seed_courses(db.connection(), sps.id); db.commit()
    n2 = seed_courses(db.connection(), sps.id); db.commit()   # second run = no-op
    total = db.execute(select(func.count()).select_from(Course).where(
        Course.tenant_id == sps.id, Course.deleted_at.is_(None))).scalar_one()
    assert n1 == 8 and n2 == 0 and total == 8
