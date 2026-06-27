"""Request dependencies: build the authoritative tenant context from the JWT."""
from __future__ import annotations

from fastapi import HTTPException, Request

from .context import RequestContext, VERTICAL, set_context
from .security import decode_access_token


def get_current_context(request: Request) -> RequestContext:
    """Verify the access-token cookie and set the request context.

    tenant_id comes from the SIGNED JWT (authoritative isolation boundary) — never
    from the Host or a raw header. business_unit_id is taken from an optional X-BU
    header (set by the Next edge from the vertical path) and validated against the
    user's memberships. Missing/invalid token → 401.
    """
    token = request.cookies.get("access_token")
    payload = decode_access_token(token) if token else None
    if not payload:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "Authentication required"},
        )

    member_bus = {m.get("business_unit_id") for m in payload.get("memberships", [])}
    bu = request.headers.get("x-bu")
    if bu is not None and bu not in member_bus and bu not in VERTICAL.values():
        # A BU the user has no membership in → forbidden.
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_BU", "message": "No access to this business unit"},
        )
    if bu is not None and bu not in member_bus:
        bu = None  # path vertical the user isn't a member of → no BU scope

    ctx = RequestContext(
        tenant_id=payload["tenant_id"],
        business_unit_id=bu,
        user_id=payload.get("sub"),
        roles=tuple(payload.get("role_flat", [])),
    )
    set_context(ctx)
    return ctx
