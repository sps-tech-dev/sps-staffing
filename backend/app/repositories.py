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


class TenantScopedRepo:
    """Every authenticated read goes through base_query → tenant-scoped."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def base_query(self, model):
        # tenant_id from the verified JWT context — the isolation boundary.
        tid = self.ctx.tenant_id
        if isinstance(tid, str):
            tid = uuid.UUID(tid)
        q = select(model).where(model.tenant_id == tid)
        # Two-axis tables also scope by business_unit_id when one is in context.
        if self.ctx.business_unit_id is not None and hasattr(model, "business_unit_id"):
            q = q.where(model.business_unit_id == self.ctx.business_unit_id)
        return q

    # Example scoped read used by the cross-tenant-leakage test: users in MY tenant.
    def list_users(self) -> list[User]:
        return list(self.db.execute(self.base_query(User)).scalars().all())
