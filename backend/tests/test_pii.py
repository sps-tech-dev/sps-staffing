"""PII encryption (Part 10): envelope encrypt/decrypt, blind index, dedup, masking."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app import crypto
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Membership, Tenant, User
from app.models_staffing import Candidate

HOST = {"host": "spstechnosoft.com"}
PW = "PiiLocal!123"
EMAIL = "pii@local.test"


# ── unit: crypto primitives ──────────────────────────────────────
def test_encrypt_decrypt_roundtrip():
    blob = crypto.encrypt("ABCDE1234F")
    assert isinstance(blob, bytes) and blob != b"ABCDE1234F"
    assert b"ABCDE1234F" not in blob          # not plaintext at rest
    assert crypto.decrypt(blob) == "ABCDE1234F"
    assert crypto.encrypt(None) is None and crypto.decrypt(None) is None


def test_encrypt_is_randomized_but_blind_index_is_deterministic():
    assert crypto.encrypt("9876543210") != crypto.encrypt("9876543210")   # random nonce
    assert crypto.blind_index("9876543210") == crypto.blind_index("9876543210")
    assert crypto.blind_index("9876543210") != crypto.blind_index("9876543211")


# ── integration: candidate write path ────────────────────────────
def _mk(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Pii", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles)); db.commit()
    return u


@pytest.fixture
def recruiter():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk(db, sps, EMAIL, ["recruiter"])
    yield sps
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == u.id))
    db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def _login(c):
    assert c.post("/api/auth/login", json={"email": EMAIL, "password": PW}, headers=HOST).status_code == 200


def test_create_candidate_stores_ciphertext_not_plaintext(recruiter):
    c = TestClient(app); _login(c)
    r = c.post("/api/candidates", json={"full_name": "Asha", "phone": "9876543210", "pan": "ABCDE1234F"}, headers=HOST)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    # at rest: the raw columns hold bytea ciphertext, NOT the plaintext
    db = get_sessionmaker()()
    row = db.execute(text("SELECT phone_enc, pan_enc, phone_bidx, pan_bidx "
                          "FROM staffing.candidates WHERE id=:id"), {"id": cid}).one()
    phone_enc, pan_enc, phone_bidx, pan_bidx = row
    assert phone_enc and b"9876543210" not in bytes(phone_enc)
    assert pan_enc and b"ABCDE1234F" not in bytes(pan_enc)
    assert phone_bidx == crypto.blind_index("9876543210")
    assert pan_bidx == crypto.blind_index("ABCDE1234F")
    # privileged reveal: ORM attribute access decrypts back to plaintext
    cand = db.get(Candidate, cid)
    assert cand.phone_enc == "9876543210" and cand.pan_enc == "ABCDE1234F"
    db.close()


def test_duplicate_phone_or_pan_rejected(recruiter):
    c = TestClient(app); _login(c)
    a = c.post("/api/candidates", json={"full_name": "Aa", "phone": "9811111111"}, headers=HOST)
    assert a.status_code == 200, a.text
    dup = c.post("/api/candidates", json={"full_name": "Bb", "phone": "9811111111"}, headers=HOST)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DUPLICATE_CANDIDATE"


def test_admin_list_masks_phone_without_decrypting(recruiter):
    c = TestClient(app); _login(c)  # recruiter lacks admin; make an admin too
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    admin = _mk(db, sps, "pii-admin@local.test", ["admin"]); db.close()
    c.post("/api/candidates", json={"full_name": "Masked", "phone": "9822222222"}, headers=HOST)

    ac = TestClient(app)
    assert ac.post("/api/auth/login", json={"email": "pii-admin@local.test", "password": PW}, headers=HOST).status_code == 200
    items = ac.get("/api/admin/candidates", headers=HOST).json()["items"]
    masked = next(i for i in items if i["full_name"] == "Masked")
    assert masked["phone"] == "••••••" and "9822222222" not in str(masked)

    db = get_sessionmaker()()
    db.execute(delete(Membership).where(Membership.user_id == admin.id))
    db.execute(delete(User).where(User.id == admin.id)); db.commit(); db.close()
