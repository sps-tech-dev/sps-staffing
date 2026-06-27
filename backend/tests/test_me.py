"""Candidate read-model endpoint: auth required + real, scoped shape."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import Tenant, User

EMAIL = "cand.overview@local.test"
PW = "CandOverview!123"
HOST = {"host": "spstechnosoft.com"}


@pytest.fixture
def candidate():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == EMAIL))
    db.add(User(tenant_id=sps.id, email=EMAIL, password_hash=PasswordHasher().hash(PW),
                full_name="Cand Overview", status="active"))
    db.commit()
    yield
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == EMAIL))
    db.commit()
    db.close()


def test_overview_requires_auth():
    r = TestClient(app).get("/api/me/overview", headers=HOST)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_overview_returns_real_scoped_shape(candidate):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": EMAIL, "password": PW}, headers=HOST).status_code == 200
    r = c.get("/api/me/overview", headers=HOST)
    assert r.status_code == 200
    body = r.json()
    for k in ("applications", "interviews", "offers", "profileComplete", "recent"):
        assert k in body
    assert body["profileComplete"] == 100  # full_name + email + active all set
    assert body["recent"] == []            # no staffing tables yet (Slice 3)
