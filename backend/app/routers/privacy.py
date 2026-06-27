"""DPDP data-principal self-service (F6 / Part 10).

Mechanisms for the logged-in user (the data principal):
- consent ledger: read current state + record grant/withdraw (append-only).
- data export: assemble the principal's data (account + linked candidate records
  + applications) and return it; the request is recorded.
- erasure: record an erasure request (status=pending). Actual erasure EXECUTION
  is deliberately NOT performed here — it needs a reviewed cascade/redaction
  policy; the mechanism (capture + audit) is what F6 delivers.

STOP-3: the legal/consent NOTICE WORDING is STUBBED (POLICY_TEXT placeholders).
`policy_version` is recorded so real notices can be versioned later. All routes
are authenticated and tenant-scoped via the request context.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models import Consent, DpdpRequest, User
from ..models_staffing import Application, Candidate

router = APIRouter()

PURPOSES = ("data_processing", "marketing", "cookies")
# STOP-3: stubbed notice version + copy. Replace POLICY_TEXT with reviewed legal
# wording before any real-user launch; bump POLICY_VERSION when the notice changes.
POLICY_VERSION = "2026-06-stub"
POLICY_TEXT = {
    "data_processing": "[LEGAL COPY TBD] Notice describing processing of your data.",
    "marketing": "[LEGAL COPY TBD] Notice describing marketing communications.",
    "cookies": "[LEGAL COPY TBD] Notice describing non-essential cookies.",
}


class ConsentBody(BaseModel):
    purpose: str
    granted: bool

    @field_validator("purpose")
    @classmethod
    def _purpose(cls, v: str) -> str:
        if v not in PURPOSES:
            raise ValueError(f"purpose must be one of {PURPOSES}")
        return v


def _uid(ctx: RequestContext) -> uuid.UUID:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Authentication required"})
    return uuid.UUID(str(ctx.user_id))


def _tid(ctx: RequestContext) -> uuid.UUID:
    return uuid.UUID(str(ctx.tenant_id))


@router.get("/consent")
def get_consent(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Current consent state — latest event per purpose for the logged-in user."""
    uid = _uid(ctx)
    rows = db.execute(
        select(Consent)
        .where(Consent.tenant_id == _tid(ctx), Consent.subject_user_id == uid)
        .order_by(Consent.created_at.desc())
    ).scalars().all()
    latest: dict[str, bool] = {}
    for c in rows:  # rows are newest-first; first seen per purpose wins
        latest.setdefault(c.purpose, c.granted)
    return {
        "policy_version": POLICY_VERSION,
        "notices": POLICY_TEXT,
        "purposes": {p: latest.get(p, False) for p in PURPOSES},
    }


@router.post("/consent")
def set_consent(body: ConsentBody, ctx: RequestContext = Depends(get_current_context),
                db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Record a consent grant/withdraw event (append-only)."""
    uid = _uid(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    row = Consent(tenant_id=_tid(ctx), subject_user_id=uid, purpose=body.purpose,
                  granted=body.granted, policy_version=POLICY_VERSION)
    db.add(row)
    db.flush()
    write_audit(db, ctx, "consent.set", "consent", row.id,
                after={"purpose": body.purpose, "granted": body.granted})
    db.commit()
    res = {"id": str(row.id), "purpose": body.purpose, "granted": body.granted,
           "policy_version": POLICY_VERSION}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


def _export_bundle(db: Session, ctx: RequestContext, user: User) -> dict:
    """Assemble the data principal's data within the tenant."""
    cands = db.execute(
        select(Candidate).where(
            Candidate.tenant_id == _tid(ctx), Candidate.deleted_at.is_(None),
            Candidate.email == user.email,
        )
    ).scalars().all()
    cand_ids = [c.id for c in cands]
    apps = []
    if cand_ids:
        apps = db.execute(
            select(Application).where(
                Application.tenant_id == _tid(ctx), Application.deleted_at.is_(None),
                Application.candidate_id.in_(cand_ids),
            )
        ).scalars().all()
    return {
        "account": {"id": str(user.id), "email": user.email, "full_name": user.full_name,
                    "status": user.status},
        "candidates": [{"id": str(c.id), "full_name": c.full_name, "email": c.email,
                        "skills": c.skills, "source": c.source} for c in cands],
        "applications": [{"id": str(a.id), "job_id": str(a.job_id), "stage": a.stage,
                          "business_unit_id": a.business_unit_id} for a in apps],
    }


@router.post("/export")
def export_data(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db),
                idempotency_key: str | None = Header(default=None)):
    """Right to access/portability — return the principal's data + record the request."""
    uid = _uid(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    user = db.execute(select(User).where(User.id == uid, User.tenant_id == _tid(ctx))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})
    bundle = _export_bundle(db, ctx, user)
    req = DpdpRequest(tenant_id=_tid(ctx), subject_user_id=uid, kind="export", status="completed",
                      detail={"counts": {"candidates": len(bundle["candidates"]),
                                         "applications": len(bundle["applications"])}})
    db.add(req)
    db.flush()
    write_audit(db, ctx, "dpdp.export", "dpdp_request", req.id)
    db.commit()
    res = {"request_id": str(req.id), "kind": "export", "status": "completed",
           "generated_for": str(uid), "data": bundle}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.post("/erase")
def request_erasure(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    """Right to erasure — RECORD a request (status=pending). Execution is not
    performed here (needs a reviewed cascade/redaction policy)."""
    uid = _uid(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    req = DpdpRequest(tenant_id=_tid(ctx), subject_user_id=uid, kind="erasure", status="pending",
                      detail={"note": "Recorded; manual review + execution pending (mechanism only)."})
    db.add(req)
    db.flush()
    write_audit(db, ctx, "dpdp.erasure_requested", "dpdp_request", req.id)
    db.commit()
    res = {"request_id": str(req.id), "kind": "erasure", "status": "pending"}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/requests")
def list_requests(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """The principal's own DPDP requests (export/erasure history)."""
    uid = _uid(ctx)
    rows = db.execute(
        select(DpdpRequest)
        .where(DpdpRequest.tenant_id == _tid(ctx), DpdpRequest.subject_user_id == uid)
        .order_by(DpdpRequest.created_at.desc())
    ).scalars().all()
    return {"items": [{"id": str(r.id), "kind": r.kind, "status": r.status,
                       "created_at": r.created_at.isoformat() if r.created_at else None}
                      for r in rows]}
