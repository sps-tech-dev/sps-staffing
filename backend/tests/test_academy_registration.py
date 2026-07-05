"""A3 academy student registration + SEPARATE student auth.

The two proofs that matter: (1) NO shared.users row is created for a student
(distinct identity); (2) CONTAINMENT in BOTH directions — an academy-student
token is bounced from staff surfaces, a staffing token is bounced from
academy-student surfaces — including for a DUAL-IDENTITY person holding both.
"""
from __future__ import annotations

import datetime as dt
import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, func, select

from app import storage
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Consent, Membership, Notification, Tenant, User
from app.models_academy import Student

HOST = {"host": "spstechnosoft.com"}
PW = "AcadReg!1234"
STAFF_ROUTES = ("/api/candidates", "/api/clients", "/api/jobs", "/api/leads", "/api/vendors",
                "/api/academy/courses", "/api/admin/candidates", "/api/employee/overview")


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def s3():
    import os
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.storage_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region})

        def upload(tenant_id, content_type="image/jpeg", body=b"fake-id-card"):
            key = f"tenant={tenant_id}/business_unit=ACADEMY/students/idcard/{uuid.uuid4()}.jpg"
            boto3.client("s3", region_name=settings.aws_region).put_object(
                Bucket=settings.storage_bucket, Key=key, Body=body, ContentType=content_type)
            return key
        yield upload


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    yield sps, db
    db.execute(delete(Notification).where(Notification.tenant_id == sps.id))
    sids = [s.id for s in db.execute(select(Student).where(Student.tenant_id == sps.id,
            Student.email.like("a3-%@local.test"))).scalars()]
    if sids:
        db.execute(delete(Consent).where(Consent.subject_student_id.in_(sids)))
    db.execute(delete(Student).where(Student.tenant_id == sps.id, Student.email.like("a3-%@local.test")))
    for u in db.execute(select(User).where(User.tenant_id == sps.id,
                                           User.email.like("a3-%@local.test"))).scalars().all():
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _reg_body(email, key, *, student_id=None, dob="2000-01-01", guardian=None):
    b = {"full_name": "A Three Student", "email": email, "phone": "+919811100022",
         "password": PW, "student_id": student_id or f"SID-{uuid.uuid4().hex[:8]}",
         "college_name": "Test College", "course_degree": "B.Tech CSE",
         "year_of_study": "3", "date_of_birth": dob, "id_card_key": key,
         "consent_data_processing": True}
    if guardian:
        b.update(guardian)
    return b


def _register(sps, s3, email, **kw):
    return TestClient(app).post("/api/academy/register/student",
        json=_reg_body(email, s3(sps.id), **kw), headers={**HOST, "captcha-token": "tok"})


def test_happy_adult_no_shared_user(env, s3):
    sps, db = env
    r = _register(sps, s3, "a3-adult@local.test")
    assert r.status_code == 200, r.text
    assert r.json()["minor"] is False
    st = db.execute(select(Student).where(Student.email == "a3-adult@local.test")).scalar_one()
    # academy credential (argon2), encrypted phone, identity, id_card, consent-on-row
    assert st.password_hash and st.password_hash.startswith("$argon2")
    assert st.password_hash != PW
    db.refresh(st)
    assert st.phone_enc == "9811100022" and st.college_name == "Test College" and st.id_card_s3_key
    assert st.user_id is None                              # bridge-only, NOT auth
    # consent is in the CANONICAL shared.consents ledger (Option A) via subject_student_id
    assert db.execute(select(func.count()).select_from(Consent).where(
        Consent.subject_student_id == st.id, Consent.purpose == "data_processing",
        Consent.granted.is_(True))).scalar_one() == 1
    # THE identity proof: NO shared.users row was created
    assert db.execute(select(func.count()).select_from(User).where(
        User.tenant_id == sps.id, User.email == "a3-adult@local.test")).scalar_one() == 0
    # two emails enqueued
    codes = {n.template_code for n in db.execute(select(Notification).where(
        Notification.idempotency_key.like(f"academy:%:{st.id}"))).scalars()}
    assert codes == {"student_welcome", "admin_new_student_application"}


def test_minor_guardian_gate(env, s3):
    sps, db = env
    minor = dt.date.today().replace(year=dt.date.today().year - 15).isoformat()
    assert _register(sps, s3, "a3-m1@local.test", dob=minor).status_code == 422
    r = _register(sps, s3, "a3-m2@local.test", dob=minor,
                  guardian={"guardian_name": "Parent", "guardian_consent": True})
    assert r.status_code == 200 and r.json()["minor"] is True
    st = db.execute(select(Student).where(Student.email == "a3-m2@local.test")).scalar_one()
    assert st.guardian_name == "Parent" and st.guardian_consent is True


def test_gates_and_dedup(env, s3):
    sps, db = env
    key = s3(sps.id)
    # no captcha → 400
    assert TestClient(app).post("/api/academy/register/student",
        json=_reg_body("a3-c@local.test", key), headers=HOST).status_code == 400
    # no consent → 422
    body = _reg_body("a3-nc@local.test", key); body["consent_data_processing"] = False
    assert TestClient(app).post("/api/academy/register/student", json=body,
        headers={**HOST, "captcha-token": "tok"}).status_code == 422
    # flag off → 404
    settings.feature_academy = False
    try:
        assert TestClient(app).post("/api/academy/register/student", json=_reg_body("a3-f@local.test", key),
            headers={**HOST, "captcha-token": "tok"}).status_code == 404
    finally:
        settings.feature_academy = True
    # dedup: same email OR same student_id → 409
    assert _register(sps, s3, "a3-dup@local.test", student_id="SID-DUP").status_code == 200
    assert _register(sps, s3, "a3-dup@local.test", student_id="SID-OTHER").status_code == 409  # email
    assert _register(sps, s3, "a3-dup2@local.test", student_id="SID-DUP").status_code == 409   # student_id


def test_email_reuses_across_boundary(env, s3):
    """A staffing shared.users email does NOT collide with academy (distinct tables)."""
    sps, db = env
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    email = "a3-cross@local.test"
    u = User(tenant_id=sps.id, email=email, password_hash=PasswordHasher().hash("StaffPw!1234"),
             full_name="Staffer", status="active")
    db.add(u); db.flush()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["recruiter"])); db.commit()
    # same email registers fine in academy (no collision)
    assert _register(sps, s3, email).status_code == 200
    # the staffing user is untouched
    db.refresh(u)
    assert u.status == "active" and u.password_hash.startswith("$argon2")


def test_academy_auth_login_and_isolation(env, s3):
    sps, db = env
    _register(sps, s3, "a3-login@local.test")
    # academy login works
    c = TestClient(app)
    r = c.post("/api/academy/auth/login",
               json={"email": "a3-login@local.test", "password": PW}, headers=HOST)
    assert r.status_code == 200 and r.json()["email"] == "a3-login@local.test"
    me = c.get("/api/academy/auth/me", headers=HOST)
    assert me.status_code == 200 and me.json()["kind"] == "academy_student"
    # a STUDENT cannot log in via the STAFFING login (not in shared.users)
    assert TestClient(app).post("/api/auth/login",
        json={"email": "a3-login@local.test", "password": PW}, headers=HOST).status_code == 401
    # a STAFFING credential cannot log in via ACADEMY auth (not in academy.students)
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    su = User(tenant_id=sps.id, email="a3-staffonly@local.test",
              password_hash=PasswordHasher().hash("StaffPw!1234"), full_name="S", status="active")
    db.add(su); db.flush(); db.add(Membership(user_id=su.id, business_unit_id=bu.id, roles=["recruiter"]))
    db.commit()
    assert TestClient(app).post("/api/academy/auth/login",
        json={"email": "a3-staffonly@local.test", "password": "StaffPw!1234"},
        headers=HOST).status_code == 401


def test_containment_both_directions_incl_dual_identity(env, s3):
    """THE security proof. A person is BOTH a staffing candidate (shared.users) and
    an academy student (academy.students) — same email, two identities, two tokens.
    Each token is bounced from the OTHER system's surfaces."""
    sps, db = env
    email = "a3-dual@local.test"
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    u = User(tenant_id=sps.id, email=email, password_hash=PasswordHasher().hash("StaffPw!1234"),
             full_name="Dual", status="active")
    db.add(u); db.flush(); db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["candidate"]))
    db.commit()
    _register(sps, s3, email)   # same email, academy identity

    # academy-student token ALONE
    stud = TestClient(app)
    stud.post("/api/academy/auth/login", json={"email": email, "password": PW}, headers=HOST)
    assert stud.get("/api/academy/auth/me", headers=HOST).status_code == 200      # works on academy
    for path in STAFF_ROUTES:                                                      # bounced from staff
        assert stud.get(path, headers=HOST).status_code in (401, 403, 404), \
            f"academy token reached staff surface {path}"

    # staffing (candidate) token ALONE
    staff = TestClient(app)
    staff.post("/api/auth/login", json={"email": email, "password": "StaffPw!1234"}, headers=HOST)
    assert staff.get("/api/academy/auth/me", headers=HOST).status_code == 401     # bounced from academy
    assert staff.get("/api/candidates", headers=HOST).status_code == 403          # candidate is low-priv staff-wise

    # dual holder: BOTH cookies in one client — each surface reads only its own cookie
    dual = TestClient(app)
    dual.post("/api/auth/login", json={"email": email, "password": "StaffPw!1234"}, headers=HOST)
    dual.post("/api/academy/auth/login", json={"email": email, "password": PW}, headers=HOST)
    assert dual.get("/api/academy/auth/me", headers=HOST).status_code == 200      # student surface OK
    assert dual.get("/api/candidates", headers=HOST).status_code == 403           # still low-priv on staff


def test_erasure_deletes_id_card(env, s3):
    sps, db = env
    key = s3(sps.id)
    TestClient(app).post("/api/academy/register/student",
        json=_reg_body("a3-erase@local.test", key), headers={**HOST, "captcha-token": "tok"})
    assert storage.head_object(key) is not None
    st = db.execute(select(Student).where(Student.email == "a3-erase@local.test")).scalar_one()
    from app import erasure
    summary = erasure.anonymize_student(db, st)
    db.commit()
    assert summary["id_card_objects_deleted"] == 1 and storage.head_object(key) is None
    db.refresh(st)
    assert st.id_card_s3_key is None and st.phone_bidx is None and st.password_hash == "!erased"
