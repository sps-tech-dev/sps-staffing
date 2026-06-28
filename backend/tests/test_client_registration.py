"""Client self-registration: pending+unlinked request, encrypted phone, gates, grants nothing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db import get_sessionmaker
from app.main import app
from app.models import ClientRegistrationRequest, ClientUser, Tenant, User

HOST = {"host": "spstechnosoft.com"}


def _payload(**over):
    base = {"company_name": "Acme Industries", "industry": "BFSI", "contact_person": "Rohan Mehta",
            "email": "rohan@acme.test", "phone": "9811100022", "website": "https://acme.test",
            "company_size": "50-200", "captcha_token": "t", "consent_data_processing": True}
    base.update(over); return base


@pytest.fixture
def clean():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    yield sps
    db.execute(delete(ClientRegistrationRequest).where(ClientRegistrationRequest.tenant_id == sps.id))
    db.commit(); db.close()


def test_captcha_gate(clean):
    c = TestClient(app)
    assert c.post("/api/register/client", json=_payload(captcha_token=""), headers=HOST).status_code == 400


def test_consent_required(clean):
    c = TestClient(app)
    r = c.post("/api/register/client", json=_payload(consent_data_processing=False), headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_bad_email_phone_422(clean):
    c = TestClient(app)
    assert c.post("/api/register/client", json=_payload(email="nope"), headers=HOST).status_code == 422
    assert c.post("/api/register/client", json=_payload(phone="123"), headers=HOST).status_code == 422


def test_creates_pending_unlinked_request_encrypted(clean):
    sps = clean
    c = TestClient(app)
    r = c.post("/api/register/client", json=_payload(), headers=HOST)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    rid = r.json()["id"]

    db = get_sessionmaker()()
    # phone encrypted at rest (ciphertext, not plaintext); bidx set
    row = db.execute(text("SELECT company_name, status, phone_enc, phone_bidx FROM "
                          "shared.client_registration_requests WHERE id=:i"), {"i": rid}).one()
    assert row[0] == "Acme Industries" and row[1] == "pending"
    assert row[2] and b"9811100022" not in bytes(row[2])   # ciphertext
    assert row[3] is not None
    # GRANTS NOTHING: no users row, hence no client_users binding → no access until approval
    assert db.execute(select(User).where(User.tenant_id == sps.id, User.email == "rohan@acme.test")).scalar_one_or_none() is None
    db.close()
