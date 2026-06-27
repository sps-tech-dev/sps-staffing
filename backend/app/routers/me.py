"""Current-user read-model endpoints (candidate self-service)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..readmodels import candidate_overview

router = APIRouter()


@router.get("/overview")
def overview(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Candidate dashboard overview — authenticated + tenant/user scoped."""
    return candidate_overview(db, ctx)
