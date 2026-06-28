"""Staffing workflow endpoints (Part 5): submissions (+ offers / interviews /
invoices / vendors in later slices). Two-axis scoped, staff-gated, idempotent."""
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
from ..models_staffing import (
    SUBMISSION_STATUSES, Application, Candidate, Job, Submission,
)
from .staffing import BU, _require_staff, _tid

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────
def _app_or_404(db: Session, ctx: RequestContext, app_id: uuid.UUID) -> Application:
    a = db.execute(select(Application).where(
        Application.id == app_id, Application.tenant_id == _tid(ctx),
        Application.business_unit_id == BU, Application.deleted_at.is_(None))).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Application not found"})
    return a


def _sub_dict(s: Submission) -> dict:
    return {"id": str(s.id), "application_id": str(s.application_id), "status": s.status,
            "client_feedback": s.client_feedback,
            "created_at": s.created_at.isoformat() if s.created_at else None}


# ── submissions ──────────────────────────────────────────────────
class FeedbackIn(BaseModel):
    status: str | None = None
    client_feedback: str | None = None

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v is not None and v not in SUBMISSION_STATUSES:
            raise ValueError(f"status must be one of {SUBMISSION_STATUSES}")
        return v


@router.post("/applications/{app_id}/submissions")
def create_submission(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Submit a candidate/application to the client."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    _app_or_404(db, ctx, app_id)  # tenant+BU ownership check
    obj = Submission(tenant_id=_tid(ctx), business_unit_id=BU, application_id=app_id,
                     status="submitted", submitted_by=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "submission.create", "submission", obj.id, after={"application_id": str(app_id)})
    db.commit()
    res = _sub_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/applications/{app_id}/submissions")
def list_app_submissions(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                         db: Session = Depends(get_db)):
    _require_staff(ctx)
    _app_or_404(db, ctx, app_id)
    rows = db.execute(select(Submission).where(
        Submission.tenant_id == _tid(ctx), Submission.business_unit_id == BU,
        Submission.application_id == app_id, Submission.deleted_at.is_(None))
        .order_by(Submission.created_at.desc())).scalars().all()
    return [_sub_dict(s) for s in rows]


@router.get("/submissions")
def list_submissions(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Submissions dashboard — tenant+BU scoped, with candidate + job names."""
    _require_staff(ctx)
    rows = db.execute(
        select(Submission, Candidate.full_name, Job.title)
        .join(Application, Application.id == Submission.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Submission.tenant_id == _tid(ctx), Submission.business_unit_id == BU,
               Submission.deleted_at.is_(None))
        .order_by(Submission.created_at.desc())
    ).all()
    return [{**_sub_dict(s), "candidate": name, "job": title} for s, name, title in rows]


@router.patch("/submissions/{submission_id}")
def update_submission(submission_id: uuid.UUID, body: FeedbackIn,
                      ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Record client feedback / status (under_review / shortlisted / rejected)."""
    _require_staff(ctx)
    s = db.execute(select(Submission).where(
        Submission.id == submission_id, Submission.tenant_id == _tid(ctx),
        Submission.business_unit_id == BU, Submission.deleted_at.is_(None))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Submission not found"})
    before = {"status": s.status}
    if body.status is not None:
        s.status = body.status
    if body.client_feedback is not None:
        s.client_feedback = body.client_feedback
    db.flush()
    write_audit(db, ctx, "submission.update", "submission", s.id, before=before,
                after={"status": s.status})
    db.commit()
    return _sub_dict(s)
