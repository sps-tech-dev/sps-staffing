"""Resume upload (B.1): presign auth/type/size gates, confirm + extraction (PDF/DOCX),
key-prefix binding, cross-tenant isolation, presigned GET, erasure S3 delete.

S3 is mocked with moto — no real AWS. The bucket is settings.storage_bucket (the
local default; deployed injects S3_BUCKET)."""
from __future__ import annotations

import io
import uuid

import boto3
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import delete, select, text

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, Consent, DpdpRequest, Membership, Tenant, User
from app.models_staffing import Application, Candidate, Client, Job

HOST = {"host": "spstechnosoft.com"}
PW = "ResumeLocal!123"
RECRUITER = "resume-rec@local.test"
SUBJECT = "resume-subject@local.test"

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ── fixtures: files ──────────────────────────────────────────────
def _mini_pdf(text_line: str = "Asha Sharma Python AWS Terraform") -> bytes:
    """Minimal valid single-page PDF with a text line (correct xref offsets)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text_line}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return bytes(out)


def _mini_docx(text_line: str = "Ravi Verma Java Spring Kubernetes") -> bytes:
    import docx
    d = docx.Document()
    d.add_paragraph(text_line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ── fixtures: env ────────────────────────────────────────────────
def _mk_user(db, tenant, email, roles):
    db.execute(delete(User).where(User.tenant_id == tenant.id, User.email == email))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Resume Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def s3(monkeypatch):
    """Mocked S3 with the app's bucket created. Clients are built per call in
    app/storage.py, so everything inside the test sees the mock."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        boto3.client("s3", region_name=settings.aws_region).create_bucket(
            Bucket=settings.storage_bucket,
            CreateBucketConfiguration={"LocationConstraint": settings.aws_region},
        )
        yield boto3.client("s3", region_name=settings.aws_region)


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    rec = _mk_user(db, sps, RECRUITER, ["recruiter"])
    yield sps
    db.execute(delete(Application).where(Application.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Candidate).where(Candidate.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _mk_candidate(c, email=None, phone="9812345670") -> str:
    r = c.post("/api/candidates", json={"full_name": "Asha Sharma", "email": email,
                                        "phone": phone}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload_via_presign(c, s3, cid, data: bytes, ctype: str) -> str:
    """presign → (simulated browser PUT via boto3) → returns the object key."""
    p = c.post(f"/api/candidates/{cid}/resume/presign",
               json={"content_type": ctype, "size_bytes": len(data)}, headers=HOST)
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["upload_url"] and body["key"].startswith("tenant=")
    s3.put_object(Bucket=settings.storage_bucket, Key=body["key"], Body=data,
                  ContentType=ctype)
    return body["key"]


# ── presign gates ────────────────────────────────────────────────
def test_presign_requires_auth_401():
    c = TestClient(app)
    r = c.post(f"/api/candidates/{uuid.uuid4()}/resume/presign",
               json={"content_type": PDF_TYPE, "size_bytes": 100}, headers=HOST)
    assert r.status_code == 401


def test_presign_requires_staff_403(env):
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    u = _mk_user(db, sps, "resume-cand-role@local.test", ["candidate"])
    try:
        c = TestClient(app); _login(c, "resume-cand-role@local.test")
        r = c.post(f"/api/candidates/{uuid.uuid4()}/resume/presign",
                   json={"content_type": PDF_TYPE, "size_bytes": 100}, headers=HOST)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()


def test_presign_rejects_wrong_content_type_422(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    r = c.post(f"/api/candidates/{cid}/resume/presign",
               json={"content_type": "image/png", "size_bytes": 100}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNSUPPORTED_TYPE"


def test_presign_rejects_oversize_422(env):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    r = c.post(f"/api/candidates/{cid}/resume/presign",
               json={"content_type": PDF_TYPE, "size_bytes": 11 * 1024 * 1024}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


# ── confirm + extraction ─────────────────────────────────────────
def _cand_resume_row(cid):
    db = get_sessionmaker()()
    row = db.execute(text("SELECT resume_s3_key, resume_text, resume_uploaded_at "
                          "FROM staffing.candidates WHERE id=:i"), {"i": cid}).one()
    db.close()
    return row


def test_confirm_pdf_sets_key_timestamp_and_text(env, s3):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    key = _upload_via_presign(c, s3, cid, _mini_pdf(), PDF_TYPE)
    r = c.post(f"/api/candidates/{cid}/resume/confirm", json={"key": key}, headers=HOST)
    assert r.status_code == 200, r.text
    assert r.json()["text_extracted"] is True
    k, txt, up = _cand_resume_row(cid)
    assert k == key and up is not None
    assert txt and "Asha Sharma" in txt and "Terraform" in txt


def test_confirm_docx_sets_text(env, s3):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    key = _upload_via_presign(c, s3, cid, _mini_docx(), DOCX_TYPE)
    r = c.post(f"/api/candidates/{cid}/resume/confirm", json={"key": key}, headers=HOST)
    assert r.status_code == 200, r.text
    _k, txt, _up = _cand_resume_row(cid)
    assert txt and "Ravi Verma" in txt and "Kubernetes" in txt


def test_confirm_rejects_foreign_key_prefix_422(env, s3):
    c = TestClient(app); _login(c, RECRUITER)
    cid_a, cid_b = _mk_candidate(c, phone="9812345671"), _mk_candidate(c, phone="9812345672")
    key_b = _upload_via_presign(c, s3, cid_b, _mini_pdf(), PDF_TYPE)
    # confirm candidate A with candidate B's key → refused
    r = c.post(f"/api/candidates/{cid_a}/resume/confirm", json={"key": key_b}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "KEY_MISMATCH"


def test_confirm_without_uploaded_object_422(env, s3):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    p = c.post(f"/api/candidates/{cid}/resume/presign",
               json={"content_type": PDF_TYPE, "size_bytes": 100}, headers=HOST).json()
    r = c.post(f"/api/candidates/{cid}/resume/confirm", json={"key": p["key"]}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "OBJECT_NOT_FOUND"


# ── download ─────────────────────────────────────────────────────
def test_get_resume_404_then_presigned_url(env, s3):
    c = TestClient(app); _login(c, RECRUITER)
    cid = _mk_candidate(c)
    assert c.get(f"/api/candidates/{cid}/resume", headers=HOST).status_code == 404
    key = _upload_via_presign(c, s3, cid, _mini_pdf(), PDF_TYPE)
    c.post(f"/api/candidates/{cid}/resume/confirm", json={"key": key}, headers=HOST)
    r = c.get(f"/api/candidates/{cid}/resume", headers=HOST)
    assert r.status_code == 200
    from urllib.parse import unquote
    url = r.json()["download_url"]
    assert url.startswith("http") and key in unquote(url)


# ── cross-tenant isolation ───────────────────────────────────────
def test_cross_tenant_candidate_not_reachable_404(env, s3):
    db = get_sessionmaker()()
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB3")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB3", slug="testb3", name="Tenant B3"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
    cand_b = Candidate(tenant_id=tb.id, full_name="Tenant B Person")
    db.add(cand_b); db.commit()
    cid_b = str(cand_b.id)
    try:
        c = TestClient(app); _login(c, RECRUITER)  # SPS001 staff
        r = c.post(f"/api/candidates/{cid_b}/resume/presign",
                   json={"content_type": PDF_TYPE, "size_bytes": 100}, headers=HOST)
        assert r.status_code == 404, "LEAK: tenant A staff can presign for tenant B's candidate"
        assert c.get(f"/api/candidates/{cid_b}/resume", headers=HOST).status_code == 404
    finally:
        db.execute(delete(Candidate).where(Candidate.tenant_id == tb.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit(); db.close()


# ── erasure deletes the S3 object + nulls the fields ─────────────
def test_erasure_deletes_resume_object_and_nulls_fields(env, s3):
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    subj = _mk_user(db, sps, SUBJECT, ["candidate"])

    rc = TestClient(app); _login(rc, RECRUITER)
    cid = _mk_candidate(rc, email=SUBJECT, phone="9812345679")
    key = _upload_via_presign(rc, s3, cid, _mini_pdf(), PDF_TYPE)
    assert rc.post(f"/api/candidates/{cid}/resume/confirm", json={"key": key},
                   headers=HOST).status_code == 200
    # object exists before erasure
    assert s3.head_object(Bucket=settings.storage_bucket, Key=key)

    try:
        sc = TestClient(app); _login(sc, SUBJECT)
        r = sc.post("/api/privacy/erase", headers=HOST)
        assert r.status_code == 200, r.text
        assert r.json()["summary"]["resume_objects_deleted"] == 1

        with pytest.raises(Exception):  # object gone from the bucket
            s3.head_object(Bucket=settings.storage_bucket, Key=key)
        k, txt, up = _cand_resume_row(cid)
        assert k is None and txt is None and up is None
    finally:
        db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
        db.execute(delete(DpdpRequest).where(DpdpRequest.tenant_id == sps.id))
        db.execute(delete(Membership).where(Membership.user_id == subj.id))
        db.execute(delete(User).where(User.id == subj.id))
        db.commit(); db.close()
