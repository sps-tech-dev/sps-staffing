"""C1-1 cross-domain auth — dev probe (runs on the dev task-def AFTER terraform sets
the cookie/CORS env). Two modes:

  setup    — assert the LIVE config is the dev-shape; assert the shared cookie seam
             emits Domain=.spstechnosoft.com; SameSite=None; Secure; HttpOnly for BOTH
             cookie names (staff + academy share the seam); create a temp staff user
             under the Host-resolved tenant so a real HTTP login can be curled.
  teardown — delete the temp staff user.

The HTTP wire assertions (Set-Cookie shape + round-trip + CORS preflight) are curled
against the LIVE dev-api between setup and teardown (curl honours cookie Domain/Secure
like a browser). sps_app.
"""
from __future__ import annotations

import sys

from argon2 import PasswordHasher
from sqlalchemy import delete, select, text
from starlette.responses import Response

from app.config import settings
from app.cookies import set_session_cookie
from app.db import get_sessionmaker
from app.models import BusinessUnit, Membership, User

TEMP_EMAIL = "c1probe-staff@local.test"
TEMP_PW = "C1Probe!12345"
HOST = "dev-api.spstechnosoft.com"


def _assert_config():
    print(f"config: cookie_domain={settings.cookie_domain!r} samesite={settings.cookie_samesite!r} "
          f"secure={settings.cookie_secure} cors={settings.cors_allowed_origins!r}")
    ok = (settings.cookie_domain == ".spstechnosoft.com" and (settings.cookie_samesite or "").lower() == "none"
          and settings.cookie_secure is True and "app-dev.spstechnosoft.com" in settings.cors_allowed_origins)
    print(f"  live config is the dev cross-domain shape: {'✅' if ok else '❌'}")
    return ok


def _assert_seam():
    good = True
    for name in ("access_token", "academy_access_token"):
        r = Response()
        set_session_cookie(r, name, "x", 900)
        sc = (r.headers.get("set-cookie") or "").lower()
        shape = ("domain=.spstechnosoft.com" in sc and "samesite=none" in sc
                 and "secure" in sc and "httponly" in sc)
        good = good and shape
        print(f"  seam[{name}]: {sc}  → {'✅' if shape else '❌'}")
    return good


def setup(db) -> int:
    a1 = _assert_config()
    print("seam emits the dev-shape for BOTH cookie names (staff + academy):")
    a2 = _assert_seam()
    from app.context import tenant_from_host
    from app.repositories import AuthQueries
    slug = tenant_from_host(HOST, settings.app_base_domain)
    tenant = AuthQueries.tenant_by_slug(db, slug)
    print(f"Host {HOST} → slug={slug!r} → tenant={tenant.code if tenant else None}")
    if tenant is None:
        print("  ❌ no tenant for the dev Host — cannot create a login user; report + adapt")
        return 1
    db.execute(delete(Membership).where(Membership.user_id.in_(
        select(User.id).where(User.email == TEMP_EMAIL, User.tenant_id == tenant.id))))
    db.execute(delete(User).where(User.email == TEMP_EMAIL, User.tenant_id == tenant.id))
    u = User(tenant_id=tenant.id, email=TEMP_EMAIL, password_hash=PasswordHasher().hash(TEMP_PW),
             full_name="C1 Probe Staff", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["recruiter"]))
    db.commit()
    print(f"TEMP_USER_READY email={TEMP_EMAIL} pw={TEMP_PW} tenant={tenant.code}")
    return 0 if (a1 and a2) else 1


def teardown(db) -> int:
    ids = [r for (r,) in db.execute(select(User.id).where(User.email == TEMP_EMAIL)).all()]
    if ids:
        db.execute(delete(Membership).where(Membership.user_id.in_(ids)))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()
    print(f"teardown: removed {len(ids)} temp user(s)")
    return 0


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    mode = sys.argv[1] if len(sys.argv) > 1 else "setup"
    return setup(db) if mode == "setup" else teardown(db)


if __name__ == "__main__":
    sys.exit(main())
