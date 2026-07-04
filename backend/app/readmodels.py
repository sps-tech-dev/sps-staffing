"""Read-models for dashboards. Computed from real, tenant-scoped DB rows.

F3a: the candidate overview is REAL now — counts derive from the candidate row
linked via candidates.user_id (the explicit 0032 link). A user with no linked
candidate degrades to zeros gracefully (valid state: login exists, no sourcing
record yet), never an error.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from .context import RequestContext
from .models import User
from .models_staffing import Application, Candidate, Interview, Job, Offer


def _linked_candidate(db, ctx: RequestContext) -> Candidate | None:
    if not ctx.user_id:
        return None
    return db.execute(select(Candidate).where(
        Candidate.tenant_id == uuid.UUID(str(ctx.tenant_id)),
        Candidate.user_id == uuid.UUID(str(ctx.user_id)),
        Candidate.deleted_at.is_(None))).scalar_one_or_none()


def candidate_overview(db, ctx: RequestContext) -> dict:
    tid = uuid.UUID(str(ctx.tenant_id))
    user = db.execute(select(User).where(
        User.tenant_id == tid, User.id == uuid.UUID(str(ctx.user_id)))).scalar_one_or_none() \
        if ctx.user_id else None

    cand = _linked_candidate(db, ctx)
    filled = [
        bool(user and user.full_name),
        bool(user and user.email),
        bool(user and user.status == "active"),
        bool(cand is not None),
        bool(cand is not None and cand.resume_s3_key),
    ]
    profile_complete = round(100 * sum(filled) / len(filled)) if user else 0

    if cand is None:   # unlinked login — zeros, gracefully (not an error)
        return {"applications": 0, "interviews": 0, "offers": 0,
                "profileComplete": profile_complete, "recent": []}

    app_ids = select(Application.id).where(
        Application.tenant_id == tid, Application.candidate_id == cand.id,
        Application.deleted_at.is_(None))
    n_apps = db.execute(select(func.count()).select_from(Application).where(
        Application.tenant_id == tid, Application.candidate_id == cand.id,
        Application.deleted_at.is_(None))).scalar_one()
    n_interviews = db.execute(select(func.count()).select_from(Interview).where(
        Interview.tenant_id == tid, Interview.application_id.in_(app_ids),
        Interview.deleted_at.is_(None))).scalar_one()
    n_offers = db.execute(select(func.count()).select_from(Offer).where(
        Offer.tenant_id == tid, Offer.application_id.in_(app_ids),
        Offer.deleted_at.is_(None))).scalar_one()
    recent_rows = db.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id)
        .where(Application.tenant_id == tid, Application.candidate_id == cand.id,
               Application.deleted_at.is_(None))
        .order_by(Application.updated_at.desc()).limit(5)).all()
    recent = [{"id": str(a.id), "job": j.title, "stage": a.stage} for a, j in recent_rows]

    return {"applications": n_apps, "interviews": n_interviews, "offers": n_offers,
            "profileComplete": profile_complete, "recent": recent}


def my_applications(db, ctx: RequestContext) -> list[dict]:
    """F3a: THIS user's applications with live stages. Unlinked user → []."""
    cand = _linked_candidate(db, ctx)
    if cand is None:
        return []
    tid = uuid.UUID(str(ctx.tenant_id))
    rows = db.execute(
        select(Application, Job).join(Job, Job.id == Application.job_id)
        .where(Application.tenant_id == tid, Application.candidate_id == cand.id,
               Application.deleted_at.is_(None))
        .order_by(Application.created_at.desc())).all()
    return [{"id": str(a.id), "job_id": str(j.id), "job": j.title, "stage": a.stage,
             "applied_at": a.created_at.isoformat() if a.created_at else None} for a, j in rows]
