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
from .crypto import EncryptedStr
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
        # Blind-index uniques enforce Part 19 dedup (one person per tenant) WITHOUT
        # storing plaintext. NULL bidx (no value supplied) is exempt by SQL NULL
        # semantics, so candidates without a phone/pan don't collide.
        sa.UniqueConstraint("tenant_id", "phone_bidx", name="uq_candidates_tenant_phone_bidx"),
        sa.UniqueConstraint("tenant_id", "pan_bidx", name="uq_candidates_tenant_pan_bidx"),
        {"schema": SCHEMA},
    )
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)  # lookup/login/dedup anchor — kept CITEXT (DECISIONS)
    # PII (Part 10): encrypted at rest via app-layer envelope encryption; the *_bidx
    # columns are deterministic HMAC blind indexes for exact-match/dedup.
    # `deferred=True` ⇒ ordinary `select(Candidate)` loads do NOT fetch/decrypt the
    # ciphertext; it is decrypted only on explicit attribute access (the privileged,
    # audited reveal path), so list/queue endpoints never bulk-decrypt PII.
    phone_enc: Mapped[str | None] = mapped_column(EncryptedStr, deferred=True)
    phone_bidx: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    pan_enc: Mapped[str | None] = mapped_column(EncryptedStr, deferred=True)
    pan_bidx: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    # Plaintext columns retained during expand/contract; dropped in the contract
    # migration once all code reads/writes the encrypted columns.
    phone: Mapped[str | None] = mapped_column(sa.Text)
    pan: Mapped[str | None] = mapped_column(sa.Text)
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
