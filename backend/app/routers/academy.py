"""Academy vertical router (A1 — shell only).

Every route depends on `require_feature("academy")`, which 404s when
FEATURE_ACADEMY is off (probe-proof, like the AI router). A1 ships only the gate
+ a health ping proving the flag works; the real surface (catalog, registration,
aptitude, pricing, payment, dashboards) arrives in A2–A9.

Importing app.models_academy here registers the academy tables on Base.metadata.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import models_academy  # noqa: F401 — registers academy tables on Base.metadata
from ..context import RequestContext
from ..features import require_feature

router = APIRouter()


@router.get("/ping")
def ping(ctx: RequestContext = Depends(require_feature("academy"))):
    """A1 gate proof: 404 when FEATURE_ACADEMY is off; 200 when on. Replaced by
    real endpoints in A2+."""
    return {"vertical": "academy", "status": "ok"}
