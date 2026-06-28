"""Public candidate registration: captcha gate, consent gate + ledger, encrypted
persist, dedup-409 (the full secure intake flow)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db import get_sessionmaker
from app.main import app
from app.models import Consent, Tenant
from app.models_staffing import Candidate

HOST = {"host": "spstechnosoft.com"}  # apex -> owner tenant SPS001


def _payload(**over):
    base = {
        "full_name": "Nikhil Rao", "email": "nikhil@example.com",
        "phone": "9765432100", "pan": "AAAPR1234C",
        "captcha_token": "test-token", "consent_data_processing": True,
    }
    base.update(over)
    return base


@pytest.fixture
def clean():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    yield sps
    cand_ids = [c.id for c in db.execute(
        select(Candidate).where(Candidate.tenant_id == sps.id)).scalars().all()]
    if cand_ids:
        db.execute(delete(Consent).where(Consent.subject_candidate_id.in_(cand_ids)))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.commit(); db.close()


def test_captcha_gate(clean):
    c = TestClient(app)
    r = c.post("/api/register/candidate", json=_payload(captcha_token=""), headers=HOST)
    assert r.status_code == 400 and r.json()["error"]["code"] == "CAPTCHA_FAILED"


def test_consent_required_to_collect_pii(clean):
    c = TestClient(app)
    r = c.post("/api/register/candidate", json=_payload(consent_data_processing=False), headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_register_persists_encrypted_and_records_consent(clean):
    sps = clean
    c = TestClient(app)
    r = c.post("/api/register/candidate", json=_payload(consent_marketing=True), headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "registered" and body["policy_version"]
    cid = body["id"]

    db = get_sessionmaker()()
    # encrypted at rest — raw columns hold ciphertext, not plaintext
    row = db.execute(text("SELECT phone_enc, pan_enc, phone_bidx FROM staffing.candidates WHERE id=:i"),
                     {"i": cid}).one()
    assert row[0] and b"9765432100" not in bytes(row[0])
    assert row[1] and b"AAAPR1234C" not in bytes(row[1])
    assert row[2] is not None  # blind index set
    # decrypt round-trip via ORM
    cand = db.get(Candidate, cid)
    assert cand.phone_enc == "9765432100" and cand.pan_enc == "AAAPR1234C"
    assert cand.source == "self_registration"
    # consent ledger recorded against the candidate (data_processing + marketing)
    purposes = {x.purpose for x in db.execute(
        select(Consent).where(Consent.subject_candidate_id == cand.id)).scalars().all()}
    assert {"data_processing", "marketing"} <= purposes
    db.close()


def test_duplicate_registration_rejected(clean):
    c = TestClient(app)
    assert c.post("/api/register/candidate", json=_payload(phone="9700011122", pan="BBBPR1234C"),
                  headers=HOST).status_code == 200
    dup = c.post("/api/register/candidate",
                 json=_payload(full_name="Other Name", email="other@example.com",
                               phone="9700011122", pan="ZZZPR9999Z"), headers=HOST)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DUPLICATE_CANDIDATE"


def test_registration_config_exposes_sitekey_and_notices(clean):
    c = TestClient(app)
    cfg = c.get("/api/register/config", headers=HOST).json()
    assert "hcaptcha_sitekey" in cfg and cfg["policy_version"]
    assert "[LEGAL COPY TBD]" in cfg["notices"]["data_processing"]
