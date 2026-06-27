"""Feature flags (F6).

Non-GA features are OFF by default and gated. A gated route returns **404** (not
403) when its feature is off, so the surface is indistinguishable from a route
that doesn't exist — clients can't probe for unreleased functionality.

Flags resolve from env-driven settings today. The per-tenant/per-plan dimension
(shared.business_units.features / shared.plans.features JSONB) can layer on later;
the gate signature (`is_enabled(name, ctx)`) already accepts a context for that.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException

from .config import settings
from .context import RequestContext
from .deps import get_current_context

# name -> resolver. Add non-GA features here; default OFF.
_RESOLVERS = {
    "ai": lambda ctx: settings.feature_ai,
}


def is_enabled(name: str, ctx: RequestContext | None = None) -> bool:
    resolver = _RESOLVERS.get(name)
    return bool(resolver and resolver(ctx))


def enabled_features(ctx: RequestContext | None = None) -> dict[str, bool]:
    return {name: is_enabled(name, ctx) for name in _RESOLVERS}


def require_feature(name: str):
    """Dependency factory: 404 when the feature is off (probe-proof gate)."""

    def _dep(ctx: RequestContext = Depends(get_current_context)) -> RequestContext:
        if not is_enabled(name, ctx):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
        return ctx

    return _dep
