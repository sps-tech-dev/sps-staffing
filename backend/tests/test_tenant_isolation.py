"""Cross-tenant leakage test — the proof that tenant isolation holds.

Seeds a throwaway tenant B (local scratch DB only) and asserts that a request
context for tenant A (SPS001) can read ONLY tenant A's rows, never tenant B's,
and vice versa. Isolation comes from TenantScopedRepo.base_query filtering by the
context's tenant_id (which, at runtime, comes from the verified JWT).
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import Tenant, User
from app.repositories import TenantScopedRepo

FOUNDER = "sandeep@spstechnosoft.com"
B_USER = "owner@testb.local"


@pytest.fixture
def db():
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def tenant_b(db):
    """Throwaway tenant B + a user — created here, deleted after (scratch DB only)."""
    t = db.execute(select(Tenant).where(Tenant.code == "TESTB")).scalar_one_or_none()
    if t is None:
        t = Tenant(code="TESTB", slug="testb", name="Test Tenant B")
        db.add(t)
        db.flush()
    if db.execute(select(User).where(User.tenant_id == t.id, User.email == B_USER)).scalar_one_or_none() is None:
        db.add(User(tenant_id=t.id, email=B_USER, password_hash="!", full_name="B Owner", status="invited"))
    db.commit()
    yield t
    db.execute(delete(User).where(User.tenant_id == t.id))
    db.execute(delete(Tenant).where(Tenant.id == t.id))
    db.commit()


def test_cross_tenant_users_isolation(db, tenant_b):
    a = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()

    # Tenant A context: must see A's users, must NOT see B's.
    ctx_a = RequestContext(tenant_id=str(a.id), business_unit_id=None)
    emails_a = {u.email for u in TenantScopedRepo(db, ctx_a).list_users()}
    assert FOUNDER in emails_a, "tenant A should see its own founder"
    assert B_USER not in emails_a, "LEAK: tenant A can see tenant B's user"

    # Tenant B context: must see B's user, must NOT see A's.
    ctx_b = RequestContext(tenant_id=str(tenant_b.id), business_unit_id=None)
    emails_b = {u.email for u in TenantScopedRepo(db, ctx_b).list_users()}
    assert B_USER in emails_b, "tenant B should see its own user"
    assert FOUNDER not in emails_b, "LEAK: tenant B can see tenant A's user"
