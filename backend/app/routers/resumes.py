"""Candidate resume upload/download (B.1) — staff-gated, tenant-scoped.

Flow: presign (validate type+declared size → short-lived PUT URL under the
candidate's canonical prefix) → client PUTs directly to S3 → confirm (verify the
key prefix + the object's REAL size, extract text server-side, persist, audit)
→ GET returns a short-lived pre-signed download URL. The bucket is never exposed;
browsers never see AWS credentials (DECISIONS 2026-06-26).
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import resume_parse, storage
from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models_staffing import Candidate
from .staffing import _require_staff, _tid

router = APIRouter()


class PresignIn(BaseModel):
    content_type: str
    size_bytes: int


class ConfirmIn(BaseModel):
    key: str


def _get_candidate(db: Session, ctx: RequestContext, candidate_id: uuid.UUID) -> Candidate:
    cand = db.execute(
        select(Candidate).where(Candidate.id == candidate_id,
                                Candidate.tenant_id == _tid(ctx),
                                Candidate.deleted_at.is_(None))
    ).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND",
                                                     "message": "Candidate not found"})
    return cand


@router.post("/candidates/{candidate_id}/resume/presign")
def presign_resume_upload(candidate_id: uuid.UUID, body: PresignIn,
                          ctx: RequestContext = Depends(get_current_context),
                          db: Session = Depends(get_db)):
    _require_staff(ctx)
    _get_candidate(db, ctx, candidate_id)
    ext = storage.RESUME_CONTENT_TYPES.get(body.content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail={
            "code": "UNSUPPORTED_TYPE",
            "message": "Resume must be PDF, DOC or DOCX",
        })
    if body.size_bytes <= 0 or body.size_bytes > storage.RESUME_MAX_BYTES:
        raise HTTPException(status_code=422, detail={
            "code": "FILE_TOO_LARGE",
            "message": f"Resume must be at most {storage.RESUME_MAX_BYTES // (1024 * 1024)} MB",
        })
    key = storage.build_candidate_resume_key(ctx.tenant_id, candidate_id, ext)
    url = storage.presign_put(key, body.content_type)
    return {"upload_url": url, "key": key, "content_type": body.content_type,
            "expires_in": storage.PRESIGN_PUT_TTL}


def _process_confirmed_upload(db: Session, ctx: RequestContext, cand: Candidate,
                              key: str, content_type: str, data: bytes) -> dict:
    """Persist the confirmed upload + extracted text, audited, in the caller's txn.

    Extraction runs SYNCHRONOUSLY today (resumes are small); this function is the
    seam for B.10 — a worker can later download+extract out-of-band and call the
    same persistence path.
    """
    cand.resume_s3_key = key
    cand.resume_uploaded_at = dt.datetime.now(dt.timezone.utc)
    cand.resume_text = resume_parse.extract_text(data, content_type) or None
    write_audit(db, ctx, "candidate.resume_upload", "candidate", cand.id,
                after={"resume_s3_key": key, "size_bytes": len(data),
                       "text_extracted": cand.resume_text is not None})
    # TODO(B.2): emit_timeline(cand.id, "ResumeUpload", {...}) once the candidate
    # timeline event store exists. Deliberately NOT built in B.1.
    return {"id": str(cand.id), "resume_s3_key": key,
            "resume_uploaded_at": cand.resume_uploaded_at.isoformat(),
            "text_extracted": cand.resume_text is not None}


@router.post("/candidates/{candidate_id}/resume/confirm")
def confirm_resume_upload(candidate_id: uuid.UUID, body: ConfirmIn,
                          ctx: RequestContext = Depends(get_current_context),
                          db: Session = Depends(get_db),
                          idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    cand = _get_candidate(db, ctx, candidate_id)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c

    # The key must sit under THIS candidate's canonical prefix — a client cannot
    # point the confirm at another tenant's/candidate's object.
    prefix = storage.candidate_resume_prefix(ctx.tenant_id, candidate_id)
    if not body.key.startswith(prefix):
        raise HTTPException(status_code=422, detail={
            "code": "KEY_MISMATCH",
            "message": "Key does not belong to this candidate",
        })

    head = storage.head_object(body.key)
    if head is None:
        raise HTTPException(status_code=422, detail={
            "code": "OBJECT_NOT_FOUND",
            "message": "No uploaded object found for this key (did the PUT succeed?)",
        })
    size = int(head.get("ContentLength", 0))
    if size <= 0 or size > storage.RESUME_MAX_BYTES:
        # presign validated the DECLARED size; this enforces the REAL one.
        storage.delete_object(body.key)
        raise HTTPException(status_code=422, detail={
            "code": "FILE_TOO_LARGE",
            "message": "Uploaded object is empty or exceeds the size limit",
        })
    content_type = head.get("ContentType") or ""
    if content_type not in storage.RESUME_CONTENT_TYPES:
        storage.delete_object(body.key)
        raise HTTPException(status_code=422, detail={
            "code": "UNSUPPORTED_TYPE",
            "message": "Uploaded object is not a PDF/DOC/DOCX",
        })

    data = storage.get_object_bytes(body.key)
    res = _process_confirmed_upload(db, ctx, cand, body.key, content_type, data)
    db.commit()
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/candidates/{candidate_id}/resume")
def get_resume_download_url(candidate_id: uuid.UUID,
                            ctx: RequestContext = Depends(get_current_context),
                            db: Session = Depends(get_db)):
    _require_staff(ctx)
    cand = _get_candidate(db, ctx, candidate_id)
    if not cand.resume_s3_key:
        raise HTTPException(status_code=404, detail={"code": "NO_RESUME",
                                                     "message": "No resume uploaded"})
    return {"download_url": storage.presign_get(cand.resume_s3_key),
            "expires_in": storage.PRESIGN_GET_TTL,
            "uploaded_at": cand.resume_uploaded_at.isoformat() if cand.resume_uploaded_at else None}
