"""Current-user read-model endpoints (candidate self-service)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..features import enabled_features
from ..readmodels import candidate_overview, my_applications

router = APIRouter()


@router.get("/overview")
def overview(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Candidate dashboard overview — authenticated + tenant/user scoped."""
    return candidate_overview(db, ctx)


@router.get("/applications")
def applications(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """F3a: the session user's applications with LIVE stages (resolved via the
    explicit candidates.user_id link). No linked candidate -> [] (valid state)."""
    return my_applications(db, ctx)


@router.get("/features")
def features(ctx: RequestContext = Depends(get_current_context)):
    """Feature flags resolved for this context — lets the client render gated
    widgets (e.g. AI) only when enabled. Authenticated."""
    return {"features": enabled_features(ctx)}
