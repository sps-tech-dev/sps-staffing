"""Shared-schema spine models (migration 0002).

All tables live in the `shared` schema. The identity spine does NOT use the
two-axis mixin (tenants has no tenant_id; users/business_units have no
business_unit_id). Decisions A–E from discovery are encoded here. Imported by
Alembic env.py so autogenerate sees these tables; NOT imported at app startup.
"""
from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import TimestampMixin, business_unit_check

SCHEMA = "shared"
_uuid_pk = lambda: mapped_column(  # noqa: E731
    UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
)


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)  # e.g. SPS001
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)  # subdomain, e.g. ampf
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)


class BusinessUnit(Base):
    __tablename__ = "business_units"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "code", name="uq_business_units_tenant_code"),
        sa.CheckConstraint(business_unit_check("code"), name="ck_business_units_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.tenants.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(sa.Text, nullable=False)  # STAFFING|ACADEMY|CONSULTING
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    features: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = {"schema": SCHEMA}

    # FK to business_units.id (UUID registry) — fine per decision A; the TEXT axis
    # is for vertical/business rows, not this identity link.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.users.id"), primary_key=True
    )
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.business_units.id"), primary_key=True
    )
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    code: Mapped[str | None] = mapped_column(sa.Text, unique=True)  # free|starter|growth|enterprise
    price_inr: Mapped[float | None] = mapped_column(sa.Numeric, nullable=True)
    period: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # monthly|annual
    limits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"  # decision E (plural)
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('trialing','active','past_due','cancelled')",
            name="ck_tenant_subscriptions_status",
        ),
        {"schema": SCHEMA},
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(  # 1:1 with tenant
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.tenants.id"), primary_key=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.plans.id"), nullable=True
    )
    status: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


class AuditLog(Base):
    # EXCEPTION (decision B): bigserial PK, append-only, no mixin/soft-delete.
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    business_unit_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # TEXT (decision A)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    entity: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
