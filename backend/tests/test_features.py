"""Feature flags (F6): gated routes 404 when off, work when on; /me/features."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import features as features_mod
from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Candidate

HOST = {"host": "spstechnosoft.com"}
PW = "FeatLocal!123"
EMAIL = "feat@local.test"


def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Feat", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def staffer():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, EMAIL, ["recruiter"])
    cand = Candidate(tenant_id=sps.id, full_name="Asha Sharma", skills=["python", "sql"], total_exp=4)
    db.add(cand); db.commit(); cid = cand.id
    yield sps, cid
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c):
    assert c.post("/api/auth/login", json={"email": EMAIL, "password": PW}, headers=HOST).status_code == 200


def test_ai_404_when_flag_off(staffer, monkeypatch):
    monkeypatch.setattr(settings, "feature_ai", False)
    _sps, cid = staffer
    c = TestClient(app); _login(c)
    # probe-proof: gated route is indistinguishable from a missing route
    assert c.get(f"/api/ai/candidate-summary/{cid}", headers=HOST).status_code == 404
    assert c.get("/api/me/features", headers=HOST).json()["features"]["ai"] is False


def test_ai_works_when_flag_on(staffer, monkeypatch):
    monkeypatch.setattr(settings, "feature_ai", True)
    _sps, cid = staffer
    c = TestClient(app); _login(c)
    r = c.get(f"/api/ai/candidate-summary/{cid}", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stub"] is True and "Asha Sharma" in body["summary"]
    assert c.get("/api/me/features", headers=HOST).json()["features"]["ai"] is True


def test_ai_requires_auth_even_when_on(monkeypatch):
    monkeypatch.setattr(settings, "feature_ai", True)
    c = TestClient(app)
    import uuid
    assert c.get(f"/api/ai/candidate-summary/{uuid.uuid4()}", headers=HOST).status_code == 401
