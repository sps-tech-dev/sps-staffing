"""Data access.

- AuthQueries: UNSCOPED lookups used ONLY by login/refresh (before a tenant
  context exists) — find the tenant from the request, then the user within it.
- TenantScopedRepo: the base repository every authenticated query goes through.
  It filters by the request context's tenant_id (the authoritative isolation
  boundary, taken from the verified JWT) and, for two-axis tables, business_unit_id.
  A query that does not go through this is a code-review failure.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .context import RequestContext
from .models import BusinessUnit, Membership, Tenant, User


class AuthQueries:
    """Unscoped — login-time only."""

    @staticmethod
    def tenant_by_slug(db: Session, slug: str) -> Tenant | None:
        return db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()

    @staticmethod
    def user_by_email(db: Session, tenant_id, email: str) -> User | None:
        return db.execute(
            select(User).where(User.tenant_id == tenant_id, User.email == email)
        ).scalar_one_or_none()

    @staticmethod
    def memberships(db: Session, user_id) -> list[tuple[str, list[str]]]:
        rows = db.execute(
            select(BusinessUnit.code, Membership.roles)
            .join(Membership, Membership.business_unit_id == BusinessUnit.id)
            .where(Membership.user_id == user_id)
        ).all()
        return [(code, list(roles or [])) for code, roles in rows]

    @staticmethod
    def active_client_binding(db: Session, user_id) -> tuple[uuid.UUID, str] | None:
        """The (client_id, role) an ACTIVE client_users row binds this user to (or None).
        Login-time only — this is what gives a client session its client scope + role. A
        'pending'/'rejected'/'suspended' row (or no row) yields NO client scope, so
        a self-registration alone grants nothing until an admin approves+binds."""
        from .models import ClientUser
        row = db.execute(
            select(ClientUser.client_id, ClientUser.role).where(
                ClientUser.user_id == user_id, ClientUser.status == "active",
                ClientUser.client_id.is_not(None))
        ).first()
        return (row[0], row[1]) if row else None


class TenantScopedRepo:
    """Every authenticated read goes through base_query → tenant-scoped (+ BU, + client)."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def base_query(self, model):
        # tenant_id from the verified JWT context — the authoritative isolation boundary.
        tid = self.ctx.tenant_id
        if isinstance(tid, str):
            tid = uuid.UUID(tid)
        q = select(model).where(model.tenant_id == tid)
        # Two-axis tables also scope by business_unit_id when one is in context.
        if self.ctx.business_unit_id is not None and hasattr(model, "business_unit_id"):
            q = q.where(model.business_unit_id == self.ctx.business_unit_id)
        # NESTED CLIENT SCOPE: a client-portal session (ctx.client_id set) can read ONLY
        # rows belonging to its own client. Enforced HERE in the base layer so it can
        # never be forgotten per-endpoint. Models without a client_id column are not
        # client-owned and are unaffected (staff sessions have client_id=None → no filter).
        cid = self.ctx.client_id
        if cid is not None and hasattr(model, "client_id"):
            if isinstance(cid, str):
                cid = uuid.UUID(cid)
            q = q.where(model.client_id == cid)
        # NESTED OWNER SCOPE: a client_manager (hiring manager) sees ONLY rows they own
        # (jobs they posted + that job's pipeline) — no cross-manager visibility. A
        # client_admin (HR) has no owner filter → all the client's jobs. Enforced here in
        # the base layer (owner_user_id denormalized onto owned models so no join needed).
        if cid is not None and self.ctx.client_role == "client_manager" and hasattr(model, "owner_user_id"):
            uid = self.ctx.user_id
            if uid is not None:
                if isinstance(uid, str):
                    uid = uuid.UUID(uid)
                q = q.where(model.owner_user_id == uid)
        return q

    def scoped_all(self, model):
        """Generic scoped read — every row of `model` visible to this context."""
        return list(self.db.execute(self.base_query(model)).scalars().all())

    # Example scoped read used by the cross-tenant-leakage test: users in MY tenant.
    def list_users(self) -> list[User]:
        return list(self.db.execute(self.base_query(User)).scalars().all())
