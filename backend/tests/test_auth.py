"""Auth endpoint integration tests (DB-backed, against the local scratch DB)."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import Tenant, User

TEST_EMAIL = "logintest@local.test"
TEST_PW = "LoginTest!123"
HOST = {"host": "spstechnosoft.com"}  # apex → owner tenant SPS001 (slug 'sps')


@pytest.fixture
def test_user():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == TEST_EMAIL))
    db.add(User(tenant_id=sps.id, email=TEST_EMAIL, password_hash=PasswordHasher().hash(TEST_PW),
                full_name="Login Test", status="active"))
    db.commit()
    yield
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == TEST_EMAIL))
    db.commit()
    db.close()


def test_login_invalid_email_returns_422_envelope():
    r = TestClient(app).post("/api/auth/login", json={"email": "not-an-email", "password": "x"}, headers=HOST)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"  # canonical envelope


def test_login_bad_credentials_401(test_user):
    r = TestClient(app).post("/api/auth/login", json={"email": TEST_EMAIL, "password": "wrongpass"}, headers=HOST)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_success_sets_cookies_and_me(test_user):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PW}, headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "candidate" and body["home"] == "/candidate"  # test user has no memberships → default
    assert "access_token" in r.cookies and "refresh_token" in r.cookies
    # /me works with the cookie jar from login
    me = c.get("/api/auth/me", headers=HOST)
    assert me.status_code == 200 and me.json()["user_id"]


def test_me_requires_auth_401():
    r = TestClient(app).get("/api/auth/me", headers=HOST)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
