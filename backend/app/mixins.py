"""Reusable declarative patterns.

- BUSINESS_UNITS / business_unit_check: the canonical TEXT enum (NOT a PG enum),
  reused by the two-axis mixin and by business_units.code (decision A).
- TimestampMixin: created_at / updated_at (timestamptz, UTC, server defaults).
- TwoAxisMixin: for FUTURE vertical/business tables ONLY — uuid PK, tenant_id,
  business_unit_id TEXT + CHECK, timestamps, soft-delete. NOT applied to the
  shared identity spine (tenants has no tenant_id, etc.).
"""
from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

# Canonical business-unit values (decision A): TEXT enum, not a PG enum, not uuid.
BUSINESS_UNITS: tuple[str, ...] = ("STAFFING", "ACADEMY", "CONSULTING")


def business_unit_check(column: str) -> str:
    """SQL CHECK expression body: <column> IN ('STAFFING','ACADEMY','CONSULTING')."""
    values = ", ".join(f"'{v}'" for v in BUSINESS_UNITS)
    return f"{column} IN ({values})"


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class TwoAxisMixin(TimestampMixin):
    """Two-axis partitioning for vertical/business tables (decision A).

    NOTE: vertical tables live in staffing/academy/consulting schemas, so each
    subclass sets its own schema. If a subclass overrides __table_args__, it must
    re-include the business_unit CHECK (use business_unit_check()).
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    @declared_attr.directive
    def __table_args__(cls):  # noqa: N805
        return (
            sa.CheckConstraint(
                business_unit_check("business_unit_id"),
                name=f"ck_{cls.__tablename__}_business_unit",
            ),
        )
