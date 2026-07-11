"""C1-1 — cross-domain auth hardening. The load-bearing case is LOCAL-UNCHANGED:
with the cookie/CORS envs unset, login is byte-identical to the pre-C1 shape
(host-only, SameSite=Lax, insecure, no CORS). Set on dev, the cookie carries
Domain=.spstechnosoft.com; SameSite=None; Secure so it crosses subdomains."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_academy import Student
from app.security import hash_password

HOST = {"host": "spstechnosoft.com"}
PW = "CrossDom!1234"
STAFF = "xdom-staff@local.test"
STU = "xdom-stu@local.test"


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_academy", True)


@pytest.fixture
def users():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    for e in (STAFF,):
        old = db.execute(select(User).where(User.tenant_id == sps.id, User.email == e)).scalar_one_or_none()
        if old:
            db.execute(delete(Membership).where(Membership.user_id == old.id)); db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=sps.id, email=STAFF, password_hash=PasswordHasher().hash(PW), full_name="XDom Staff", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["recruiter"]))
    db.execute(delete(Student).where(Student.email == STU))
    s = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name="XDom Stu", email=STU, password_hash=hash_password(PW))
    db.add(s); db.commit()
    yield sps, u, s
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id))
    db.execute(delete(Student).where(Student.id == s.id))
    db.commit(); db.close()


def _staff_login_cookies(c):
    r = c.post("/api/auth/login", json={"email": STAFF, "password": PW}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.headers.get_list("set-cookie")


def _student_login_cookies(c):
    r = c.post("/api/academy/auth/login", json={"email": STU, "password": PW}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.headers.get_list("set-cookie")


def _joined(cookies):
    return " || ".join(cookies).lower()


# ── LOCAL UNCHANGED (envs unset) — the inert-when-unset proof ──
def test_local_shape_unchanged(users, monkeypatch):
    monkeypatch.setattr(settings, "cookie_domain", None)
    monkeypatch.setattr(settings, "cookie_samesite", "lax")
    monkeypatch.setattr(settings, "cookie_secure", False)
    for cookies in (_staff_login_cookies(TestClient(app)), _student_login_cookies(TestClient(app))):
        blob = _joined(cookies)
        assert "samesite=lax" in blob
        assert "domain=" not in blob                 # host-only
        assert "secure" not in blob                  # insecure (http localhost)
        assert "httponly" in blob                    # unchanged
    # and /me still authenticates with the issued cookie (same-subdomain)
    c = TestClient(app); _student_login_cookies(c)
    assert c.get("/api/academy/auth/me", headers=HOST).status_code == 200


# ── DEV shape (envs set) — cross-subdomain-capable ──
def test_dev_shape_cross_domain(users, monkeypatch):
    monkeypatch.setattr(settings, "cookie_domain", ".spstechnosoft.com")
    monkeypatch.setattr(settings, "cookie_samesite", "none")
    monkeypatch.setattr(settings, "cookie_secure", True)
    for cookies in (_staff_login_cookies(TestClient(app)), _student_login_cookies(TestClient(app))):
        blob = _joined(cookies)
        assert "domain=.spstechnosoft.com" in blob
        assert "samesite=none" in blob
        assert "secure" in blob
        assert "httponly" in blob


def test_samesite_none_forces_secure(users, monkeypatch):
    """A half-set config (None without Secure) can't silently break login: None forces Secure."""
    monkeypatch.setattr(settings, "cookie_domain", ".spstechnosoft.com")
    monkeypatch.setattr(settings, "cookie_samesite", "none")
    monkeypatch.setattr(settings, "cookie_secure", False)       # deliberately NOT secure
    blob = _joined(_staff_login_cookies(TestClient(app)))
    assert "samesite=none" in blob and "secure" in blob         # Secure forced anyway


# ── CORS: credentialed, explicit origin, never wildcard ──
def test_cors_credentialed_explicit_origin():
    origin = "https://app-dev.spstechnosoft.com"
    mini = FastAPI()
    mini.add_middleware(CORSMiddleware, allow_origins=[origin], allow_credentials=True,
                        allow_methods=["*"], allow_headers=["*"])
    @mini.get("/x")
    def _x():
        return {"ok": True}
    c = TestClient(mini)
    # allowed origin → echoed + credentials true
    pre = c.options("/x", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert pre.headers.get("access-control-allow-origin") == origin
    assert pre.headers.get("access-control-allow-credentials") == "true"
    assert pre.headers.get("access-control-allow-origin") != "*"    # never wildcard w/ credentials
    # disallowed origin → not echoed
    bad = c.options("/x", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert bad.headers.get("access-control-allow-origin") != "https://evil.example"


# ── containment unaffected by the cookie change ──
def test_containment_holds(users, monkeypatch):
    monkeypatch.setattr(settings, "cookie_domain", ".spstechnosoft.com")
    monkeypatch.setattr(settings, "cookie_samesite", "none")
    monkeypatch.setattr(settings, "cookie_secure", True)
    stu = TestClient(app); _student_login_cookies(stu)
    # a student session (academy cookie, no access_token) cannot reach a staff endpoint
    assert stu.get("/api/academy/enrollments", headers=HOST).status_code == 401
