"""Staffing vertical models (Part 5) — `staffing` schema, two-axis scoped.

clients · jobs · candidates · applications. Every table carries the TwoAxisMixin
columns (id, tenant_id, business_unit_id TEXT+CHECK, created_at, updated_at,
deleted_at). business_unit_id is 'STAFFING' for these rows.
"""
from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import TenantScopedMixin, TwoAxisMixin, bu_check

SCHEMA = "staffing"

# Pipeline state machine (Part 5). Illegal transitions are enforced in the
# service layer; this CHECK bounds the allowed set of values.
APPLICATION_STAGES = (
    "sourced", "screened", "assessed", "submitted",
    "interview", "offer", "placed", "rejected", "on_hold",
)
_STAGES_SQL = ", ".join(f"'{s}'" for s in APPLICATION_STAGES)


class Client(TwoAxisMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (
        bu_check("clients"),
        sa.Index("ix_clients_tenant_bu", "tenant_id", "business_unit_id"),
        {"schema": SCHEMA},
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))


class Job(TwoAxisMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        bu_check("jobs"),
        sa.Index("ix_jobs_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_jobs_client_id", "client_id"),
        {"schema": SCHEMA},
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    jd_text: Mapped[str | None] = mapped_column(sa.Text)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(sa.Text))
    min_exp: Mapped[int | None] = mapped_column(sa.Integer)
    max_exp: Mapped[int | None] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'open'"))


class Candidate(TenantScopedMixin, Base):
    # TENANT-scoped talent pool (see DECISIONS: candidate scoping). One record per
    # person per tenant; vertical ownership lives on applications.business_unit_id,
    # so a candidate is considerable across verticals without duplication.
    __tablename__ = "candidates"
    __table_args__ = (
        sa.Index("ix_candidates_tenant", "tenant_id"),
        sa.Index("ix_candidates_search", "search_doc", postgresql_using="gin"),
        sa.Index("ix_candidates_skills", "skills", postgresql_using="gin"),
        {"schema": SCHEMA},
    )
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(sa.Text)
    pan: Mapped[str | None] = mapped_column(sa.Text)  # PII — app-layer validated; encrypt later (Part 10)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(sa.Text))
    total_exp: Mapped[float | None] = mapped_column(sa.Numeric)
    resume_s3_key: Mapped[str | None] = mapped_column(sa.Text)
    source: Mapped[str | None] = mapped_column(sa.Text)
    search_doc: Mapped[str | None] = mapped_column(TSVECTOR)  # Part 20 FTS (trigger added later)


class Application(TwoAxisMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        bu_check("applications"),
        sa.CheckConstraint(f"stage IN ({_STAGES_SQL})", name="ck_applications_stage"),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_applications_job_candidate"),
        sa.Index("ix_applications_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_applications_job_id", "job_id"),
        sa.Index("ix_applications_candidate_id", "candidate_id"),
        {"schema": SCHEMA},
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.jobs.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.candidates.id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'sourced'"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
