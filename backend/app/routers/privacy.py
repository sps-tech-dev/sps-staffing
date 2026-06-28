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
from sqlalchemy.orm import Session, undefer

from .. import erasure
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
    """Assemble the data principal's OWN data within the tenant.

    Scope: candidates are matched to the principal by (tenant_id, email) — only the
    principal's own records, never another candidate's. This is the privileged
    self-export decryption path: it DOES include the principal's own decrypted
    phone/pan (the *_enc columns are normally deferred; we undefer them here so they
    are decrypted for this bundle). Admin/other views stay masked.
    """
    cands = db.execute(
        select(Candidate)
        .options(undefer(Candidate.phone_enc), undefer(Candidate.pan_enc))
        .where(
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
                        "phone": c.phone_enc, "pan": c.pan_enc,  # decrypted — principal's own
                        "skills": c.skills, "source": c.source} for c in cands],
        "applications": [{"id": str(a.id), "job_id": str(a.job_id), "stage": a.stage,
                          "business_unit_id": a.business_unit_id} for a in apps],
    }


@router.post("/export")
def export_data(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Right to access/portability — return the principal's OWN data (incl. their
    decrypted PAN/phone) + record the request and an audited PII-disclosure entry.

    NOT idempotency-cached on purpose: the bundle contains decrypted PII, which must
    not be written to Redis; and each export is a legitimate, separately-audited
    disclosure event.
    """
    uid = _uid(ctx)
    user = db.execute(select(User).where(User.id == uid, User.tenant_id == _tid(ctx))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})
    bundle = _export_bundle(db, ctx, user)
    pii_count = sum(1 for c in bundle["candidates"] if c["phone"] or c["pan"])
    req = DpdpRequest(tenant_id=_tid(ctx), subject_user_id=uid, kind="export", status="completed",
                      detail={"counts": {"candidates": len(bundle["candidates"]),
                                         "applications": len(bundle["applications"])}})
    db.add(req)
    db.flush()
    # Privileged decryption disclosure — record WHO exported their own PII and WHEN.
    write_audit(db, ctx, "dpdp.export", "dpdp_request", req.id,
                after={"pii_disclosed": True, "candidates_with_pii": pii_count})
    db.commit()
    return {"request_id": str(req.id), "kind": "export", "status": "completed",
            "generated_for": str(uid), "data": bundle}


@router.post("/erase")
def request_erasure(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    """Right to erasure (Stage 1). DISABLE immediately (soft-delete the principal's
    candidates), then: legal-hold → exempt (manual approval required); otherwise
    AUTO-APPROVE → anonymize irreversibly → retain de-identified records → audit."""
    uid = _uid(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    user = db.execute(select(User).where(User.id == uid, User.tenant_id == _tid(ctx))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    req = DpdpRequest(tenant_id=_tid(ctx), subject_user_id=uid, kind="erasure", status=erasure.PENDING,
                      detail={"note": "disable-on-request; anonymize-on-approval (Stage 1)"})
    db.add(req)
    db.flush()

    # 1) disable immediately (reversible window) — before/independent of anonymization
    disabled = erasure.soft_delete_candidates(db, ctx, user.email)
    write_audit(db, ctx, "dpdp.erasure_requested", "dpdp_request", req.id,
                after={"candidates_disabled": disabled})

    # 2) legal-hold gate — held requests are EXEMPT and need explicit manual approval
    if erasure.under_legal_hold(db, ctx, user):
        req.legal_hold = True
        req.status = erasure.LEGAL_HOLD
        db.commit()
        res = {"request_id": str(req.id), "kind": "erasure", "status": req.status,
               "candidates_disabled": disabled, "legal_hold": True}
        store(str(ctx.tenant_id), idempotency_key, res)
        return res

    # 3) normal → auto-approve (explicit transition) → anonymize
    req.status = erasure.APPROVED
    db.flush()
    summary = erasure.run_erasure(db, ctx, req, user)
    db.commit()
    res = {"request_id": str(req.id), "kind": "erasure", "status": req.status,
           "candidates_disabled": disabled, "summary": summary}
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
