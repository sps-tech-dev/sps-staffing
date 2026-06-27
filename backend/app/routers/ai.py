"""AI assistive widgets (F6) — gated behind the `ai` feature flag.

Every route depends on `require_feature("ai")`, which 404s when the flag is off
(default in dev) — so the surface is probe-proof. When enabled, these return
DETERMINISTIC STUB insights (no model call yet); wiring a real model/provider is
later work. Auth + tenant scoping still apply via the injected context.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..features import require_feature
from ..models_staffing import Candidate

router = APIRouter()


@router.get("/candidate-summary/{candidate_id}")
def candidate_summary(candidate_id: uuid.UUID,
                      ctx: RequestContext = Depends(require_feature("ai")),
                      db: Session = Depends(get_db)):
    """Assistive candidate summary (STUB). Tenant-scoped read."""
    cand = db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.tenant_id == uuid.UUID(str(ctx.tenant_id)),
            Candidate.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Candidate not found"})
    skills = cand.skills or []
    exp = float(cand.total_exp) if cand.total_exp is not None else 0.0
    return {
        "candidate_id": str(cand.id),
        "stub": True,
        "summary": (
            f"{cand.full_name} — {exp:g} yrs experience"
            + (f", core skills: {', '.join(skills[:5])}." if skills else ".")
        ),
        "highlights": skills[:5],
        "disclaimer": "AI-assisted draft (stub). Review before use.",
    }
