"""S3 storage helpers (B.1) — pre-signed URLs only; the bucket is never exposed.

Access model (DECISIONS 2026-06-26): private bucket, task-role credentials, clients
up/download exclusively via short-lived pre-signed URLs. Key prefix mirrors the DB
two-axis partitioning: tenant=<tenant_id>/business_unit=<vertical>/<entity>/<file>,
which keeps per-tenant DPDP export/erase and lifecycle scoping straightforward.

The boto3 client is created per call (not cached at import) so test mocks (moto)
and credential refreshes always apply. These helpers make NO decisions about auth
or tenancy — callers must already be tenant-scoped.
"""
from __future__ import annotations

import uuid

import boto3

from .config import settings

# Short expiries — links are minted per request, never stored.
PRESIGN_PUT_TTL = 300   # seconds
PRESIGN_GET_TTL = 300

RESUME_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# content-type → canonical extension for the object key.
RESUME_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def _client():
    # dev/prod (s3_endpoint_url unset) → EXACTLY as before: real S3, task-role creds,
    # virtual-host addressing, bucket-default KMS. The override branch is LOCAL-ONLY
    # (MinIO): a custom endpoint needs path-style addressing.
    if settings.s3_endpoint_url:
        from botocore.config import Config
        return boto3.client("s3", region_name=settings.aws_region,
                            endpoint_url=settings.s3_endpoint_url,
                            config=Config(s3={"addressing_style": "path"}))
    return boto3.client("s3", region_name=settings.aws_region)


def _presign_client():
    # Presigned URLs must carry a host the BROWSER can reach. dev/prod (both endpoint
    # vars unset) → IDENTICAL to _client()'s real-S3 branch. Local → the published
    # MinIO port (localhost:9000) so the browser PUT/GET resolves.
    public = settings.s3_public_endpoint_url or settings.s3_endpoint_url
    if public:
        from botocore.config import Config
        return boto3.client("s3", region_name=settings.aws_region, endpoint_url=public,
                            config=Config(s3={"addressing_style": "path"}))
    return boto3.client("s3", region_name=settings.aws_region)


def build_candidate_resume_key(tenant_id: str | uuid.UUID, candidate_id: str | uuid.UUID,
                               ext: str) -> str:
    """Canonical resume key. A fresh uuid per upload — identifiable, never 'resume.pdf';
    old objects are superseded (bucket is versioned; erasure deletes by stored key)."""
    return (f"tenant={tenant_id}/business_unit=STAFFING/candidates/{candidate_id}/"
            f"{uuid.uuid4()}.{ext}")


def candidate_resume_prefix(tenant_id: str | uuid.UUID, candidate_id: str | uuid.UUID) -> str:
    """The only prefix a candidate's resume keys may live under — confirm() verifies
    the client-echoed key against this so a key can't point at another object."""
    return f"tenant={tenant_id}/business_unit=STAFFING/candidates/{candidate_id}/"


def presign_put(key: str, content_type: str, expires: int = PRESIGN_PUT_TTL) -> str:
    """Pre-signed PUT. Binds ContentType into the signature (a PUT with a different
    Content-Type header fails the signature). Size cannot be bound into a presigned
    PUT — the declared size is validated at presign time and the REAL size is
    re-checked server-side at confirm() via head_object."""
    return _presign_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.storage_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presign_get(key: str, expires: int = PRESIGN_GET_TTL) -> str:
    return _presign_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket, "Key": key},
        ExpiresIn=expires,
    )


def head_object(key: str) -> dict | None:
    """Metadata for an object (None if it doesn't exist). Used by confirm() to prove
    the upload happened and to enforce the size cap server-side."""
    try:
        return _client().head_object(Bucket=settings.storage_bucket, Key=key)
    except Exception:  # noqa: BLE001 — missing/forbidden both mean "not confirmable"
        return None


def get_object_bytes(key: str) -> bytes:
    body = _client().get_object(Bucket=settings.storage_bucket, Key=key)["Body"]
    try:
        return body.read()
    finally:
        body.close()


def delete_object(key: str) -> None:
    """Delete an object (erasure path). Task role has s3:DeleteObject (Project/s3.tf)."""
    _client().delete_object(Bucket=settings.storage_bucket, Key=key)
