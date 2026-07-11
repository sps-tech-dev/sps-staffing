"""C1-1 — the single session-cookie seam (staff + academy both route through it).

Env-driven, inert-when-unset: with COOKIE_DOMAIN/COOKIE_SAMESITE/COOKIE_SECURE
unset (local dev), a cookie is host-only + SameSite=Lax + insecure — byte-identical
to the pre-C1 shape. Set on dev/staging (`.spstechnosoft.com` / none / true), a
cookie set by dev-api.spstechnosoft.com is sent to a frontend on
app-dev.spstechnosoft.com. HttpOnly is always on.

Safety invariant: SameSite=None is invalid without Secure (browsers drop it), so
`none` FORCES Secure regardless of COOKIE_SECURE — a half-set config can't silently
break login. Deletion must echo the same Domain/Path or the browser won't clear the
cookie, so delete routes through here too.
"""
from __future__ import annotations

from fastapi import Response

from .config import settings


def _cookie_kwargs() -> dict:
    samesite = (settings.cookie_samesite or "lax").lower()
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    secure = settings.cookie_secure or samesite == "none"   # None REQUIRES Secure
    kw: dict = {"httponly": True, "secure": secure, "samesite": samesite, "path": "/"}
    if settings.cookie_domain:
        kw["domain"] = settings.cookie_domain
    return kw


def set_session_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(key=name, value=value, max_age=max_age, **_cookie_kwargs())


def delete_session_cookie(resp: Response, name: str) -> None:
    kw = _cookie_kwargs()
    # match Domain + Path (+ samesite/secure) so the browser actually clears it
    resp.delete_cookie(key=name, path="/", domain=kw.get("domain"),
                       samesite=kw["samesite"], secure=kw["secure"], httponly=True)
