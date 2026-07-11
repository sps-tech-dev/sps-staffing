"""Auth endpoints: login / refresh / logout / me. httpOnly JWT cookies, argon2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from ..validation import validate_email
from sqlalchemy.orm import Session

from ..config import settings
from ..cookies import delete_session_cookie, set_session_cookie
from ..context import RequestContext, tenant_from_host
from ..db import get_db
from ..deps import get_current_context
from ..repositories import AuthQueries
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)

router = APIRouter()

# Backend role slugs (Part 4 matrix) → frontend portal role + home route.
_PORTAL_ROLE = {
    "owner": "admin", "super_admin": "admin", "admin": "admin",
    "business_manager": "employee", "manager": "employee", "recruiter": "employee",
    "trainer": "employee", "consultant": "employee", "coordinator": "employee", "employee": "employee",
    "client": "client", "candidate": "candidate", "student": "candidate",
}
_HOME = {"candidate": "/candidate", "client": "/client", "employee": "/employee", "admin": "/admin/dashboard"}


class LoginBody(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return validate_email(v)


def _portal_role(memberships: list[tuple[str, list[str]]]) -> str:
    flat = {r.lower() for _, roles in memberships for r in roles}
    for backend_role, portal in [
        ("owner", "admin"), ("super_admin", "admin"), ("admin", "admin"),
        ("recruiter", "employee"), ("manager", "employee"), ("business_manager", "employee"),
        ("trainer", "employee"), ("consultant", "employee"), ("coordinator", "employee"), ("employee", "employee"),
        ("client", "client"), ("candidate", "candidate"), ("student", "candidate"),
    ]:
        if backend_role in flat:
            return portal
    return "candidate"


def _set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    # C1-1: the cross-domain-capable seam (env-driven; local shape when unset).
    set_session_cookie(resp, name, value, max_age)


def _build_claims(user, tenant, memberships, binding=None):
    """binding = (client_id, client_role) for an active client session, else None."""
    role_flat = sorted({r for _, roles in memberships for r in roles})
    claims = {
        "sub": str(user.id),
        "tenant_id": str(tenant.id),       # UUID — authoritative scoping key
        "tenant_code": tenant.code,
        "tenant_slug": tenant.slug,
        "role": _portal_role(memberships),
        "role_flat": role_flat,
        "memberships": [{"business_unit_id": code, "roles": roles} for code, roles in memberships],
    }
    # Client-portal session: bind the client scope + internal role into the JWT. An ACTIVE
    # client_users row produces this (the approval gate); without it there is no client scope.
    if binding is not None:
        client_id, client_role = binding
        claims["client_id"] = str(client_id)
        claims["client_role"] = client_role
        claims["role"] = "client"
        if "client" not in role_flat:
            claims["role_flat"] = sorted(set(role_flat) | {"client"})
    return claims


def _invalid():
    # Same message for unknown user / bad password / inactive — no enumeration.
    raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"})


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    slug = tenant_from_host(request.headers.get("host", settings.app_base_domain), settings.app_base_domain)
    tenant = AuthQueries.tenant_by_slug(db, slug)
    if tenant is None:
        _invalid()
    user = AuthQueries.user_by_email(db, tenant.id, body.email)
    if user is None or user.status != "active" or not verify_password(user.password_hash, body.password):
        _invalid()
    memberships = AuthQueries.memberships(db, user.id)
    binding = AuthQueries.active_client_binding(db, user.id)
    claims = _build_claims(user, tenant, memberships, binding=binding)
    _set_cookie(response, "access_token", create_access_token(claims), settings.access_ttl_seconds)
    _set_cookie(response, "refresh_token",
                create_refresh_token({"sub": claims["sub"], "tenant_id": claims["tenant_id"]}),
                settings.refresh_ttl_seconds)
    return {"user": {"id": claims["sub"], "email": str(user.email), "name": user.full_name},
            "role": claims["role"], "home": _HOME[claims["role"]]}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    payload = decode_refresh_token(request.cookies.get("refresh_token") or "")
    if not payload:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Invalid refresh token"})
    from ..models import Tenant, User  # local import keeps app boot light
    tenant = db.get(Tenant, payload["tenant_id"])
    user = db.get(User, payload["sub"])
    if tenant is None or user is None or user.status != "active":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "Session no longer valid"})
    claims = _build_claims(user, tenant, AuthQueries.memberships(db, user.id),
                           binding=AuthQueries.active_client_binding(db, user.id))
    _set_cookie(response, "access_token", create_access_token(claims), settings.access_ttl_seconds)
    return {"ok": True, "role": claims["role"]}


@router.post("/logout")
def logout(response: Response):
    for name in ("access_token", "refresh_token"):
        delete_session_cookie(response, name)   # C1-1: echo Domain/Path so it actually clears
    return {"ok": True}


@router.get("/me")
def me(ctx: RequestContext = Depends(get_current_context), request: Request = None):
    token = request.cookies.get("access_token") if request else None
    from ..security import decode_access_token
    payload = decode_access_token(token) if token else {}
    return {
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "tenant_code": payload.get("tenant_code"),
        "role": payload.get("role"),
        "memberships": payload.get("memberships", []),
        "business_unit": ctx.business_unit_id,
        "client_id": ctx.client_id,
        "client_role": ctx.client_role,   # client_admin (HR) | client_manager | null
    }
