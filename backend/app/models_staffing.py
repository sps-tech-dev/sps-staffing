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
        sa.Index("ix_jobs_owner_user_id", "owner_user_id"),
        {"schema": SCHEMA},
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )
    # The client portal user who posted/owns this job (soft ref to shared.users). Drives
    # client_manager owner-scoping. NULL for staff-created jobs (no client owner).
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
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
    # (legacy plaintext phone/pan columns dropped in migration 0008 — contract)
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
        sa.Index("ix_applications_client_id", "client_id"),
        sa.Index("ix_applications_owner_user_id", "owner_user_id"),
        {"schema": SCHEMA},
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.jobs.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.candidates.id"), nullable=False
    )
    # Denormalized owning client (from the job) so the base repo can client-scope
    # the pipeline without a join — nested client isolation can't be forgotten.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )
    # Denormalized owning client USER (from the job) → client_manager owner-scoping.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'sourced'"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # recruiter (internal)


# Submission to client (Part 5): submissions(application_id, client_feedback, status)
SUBMISSION_STATUSES = ("submitted", "under_review", "shortlisted", "rejected")
_SUB_SQL = ", ".join(f"'{s}'" for s in SUBMISSION_STATUSES)


class Submission(TwoAxisMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        bu_check("submissions"),
        sa.CheckConstraint(f"status IN ({_SUB_SQL})", name="ck_submissions_status"),
        sa.Index("ix_submissions_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_submissions_application_id", "application_id"),
        sa.Index("ix_submissions_client_id", "client_id"),
        sa.Index("ix_submissions_owner_user_id", "owner_user_id"),
        {"schema": SCHEMA},
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )  # denormalized owning client (nested isolation)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # owning client user
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'submitted'"))
    client_feedback: Mapped[str | None] = mapped_column(sa.Text)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


# Offer (Part 5): offers(application_id, ctc, joining_date, rtr_signed_at) + acceptance
OFFER_STATUSES = ("draft", "released", "accepted", "declined", "withdrawn")
_OFFER_SQL = ", ".join(f"'{s}'" for s in OFFER_STATUSES)


class Offer(TwoAxisMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        bu_check("offers"),
        sa.CheckConstraint(f"status IN ({_OFFER_SQL})", name="ck_offers_status"),
        sa.Index("ix_offers_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_offers_application_id", "application_id"),
        sa.Index("ix_offers_client_id", "client_id"),
        sa.Index("ix_offers_owner_user_id", "owner_user_id"),
        {"schema": SCHEMA},
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )  # denormalized owning client (nested isolation)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # owning client user
    ctc: Mapped[float | None] = mapped_column(sa.Numeric)          # annual CTC (INR)
    joining_date: Mapped[datetime.date | None] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'draft'"))
    rtr_signed_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))  # Right-to-Represent
    accepted_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))


# Interview (Part 5): schedule + track interviews against applications
INTERVIEW_STATUSES = ("scheduled", "completed", "cancelled", "no_show")
INTERVIEW_MODES = ("phone", "video", "onsite")
_IV_STATUS_SQL = ", ".join(f"'{s}'" for s in INTERVIEW_STATUSES)
_IV_MODE_SQL = ", ".join(f"'{s}'" for s in INTERVIEW_MODES)


class Interview(TwoAxisMixin, Base):
    __tablename__ = "interviews"
    __table_args__ = (
        bu_check("interviews"),
        sa.CheckConstraint(f"status IN ({_IV_STATUS_SQL})", name="ck_interviews_status"),
        sa.CheckConstraint(f"mode IN ({_IV_MODE_SQL})", name="ck_interviews_mode"),
        sa.Index("ix_interviews_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_interviews_application_id", "application_id"),
        sa.Index("ix_interviews_client_id", "client_id"),
        sa.Index("ix_interviews_owner_user_id", "owner_user_id"),
        {"schema": SCHEMA},
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )  # denormalized owning client (nested isolation)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # owning client user
    scheduled_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'video'"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'scheduled'"))
    interviewer_name: Mapped[str | None] = mapped_column(sa.Text)
    feedback: Mapped[str | None] = mapped_column(sa.Text)


# Invoice (Part 5): invoices(client_id, placement_id, amount, status). Placement =
# the placed application (accepted offer). The 15% placement fee is the SPS business
# term (configurable per invoice). GST/TDS are TAX rates that are NULL until legally
# confirmed (PENDING — Q1); they are NEVER hardcoded/defaulted here.
INVOICE_STATUSES = ("draft", "issued", "paid", "cancelled")
_INV_SQL = ", ".join(f"'{s}'" for s in INVOICE_STATUSES)
DEFAULT_FEE_PERCENT = 15  # SPS placement fee (business model), not a tax


class Invoice(TwoAxisMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        bu_check("invoices"),
        sa.CheckConstraint(f"status IN ({_INV_SQL})", name="ck_invoices_status"),
        sa.Index("ix_invoices_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_invoices_client_id", "client_id"),
        {"schema": SCHEMA},
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"), nullable=False
    )  # the placement (placed application)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )
    base_amount: Mapped[float | None] = mapped_column(sa.Numeric)        # billing base (e.g. CTC)
    fee_percent: Mapped[float] = mapped_column(sa.Numeric, nullable=False, server_default=sa.text("15"))
    fee_amount: Mapped[float | None] = mapped_column(sa.Numeric)          # base * fee_percent
    # TAX — configurable/stubbed; NULL until legal confirms rates (Q1). Not defaulted.
    gst_percent: Mapped[float | None] = mapped_column(sa.Numeric)
    gst_amount: Mapped[float | None] = mapped_column(sa.Numeric)
    tds_percent: Mapped[float | None] = mapped_column(sa.Numeric)
    tds_amount: Mapped[float | None] = mapped_column(sa.Numeric)
    total_amount: Mapped[float | None] = mapped_column(sa.Numeric)
    currency: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'INR'"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'draft'"))


# Vendor / sub-vendor management (Part 5) — core: vendors + vendor_submissions.
# (vendor_contracts / vendor_commissions / vendor_performance are a tracked follow-up.)
VENDOR_STATUSES = ("active", "inactive")
VENDOR_SUB_STATUSES = ("submitted", "shortlisted", "rejected", "placed")
_VEND_SQL = ", ".join(f"'{s}'" for s in VENDOR_STATUSES)
_VSUB_SQL = ", ".join(f"'{s}'" for s in VENDOR_SUB_STATUSES)


class Vendor(TwoAxisMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (
        bu_check("vendors"),
        sa.CheckConstraint(f"status IN ({_VEND_SQL})", name="ck_vendors_status"),
        sa.Index("ix_vendors_tenant_bu", "tenant_id", "business_unit_id"),
        {"schema": SCHEMA},
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(CITEXT)      # business contact (not candidate PII)
    contact_phone: Mapped[str | None] = mapped_column(sa.Text)     # business contact
    commission_percent: Mapped[float | None] = mapped_column(sa.Numeric)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))


class VendorSubmission(TwoAxisMixin, Base):
    __tablename__ = "vendor_submissions"
    __table_args__ = (
        bu_check("vendor_submissions"),
        sa.CheckConstraint(f"status IN ({_VSUB_SQL})", name="ck_vendor_submissions_status"),
        sa.Index("ix_vendor_submissions_tenant_bu", "tenant_id", "business_unit_id"),
        sa.Index("ix_vendor_submissions_vendor_id", "vendor_id"),
        {"schema": SCHEMA},
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.candidates.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.jobs.id"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'submitted'"))
    notes: Mapped[str | None] = mapped_column(sa.Text)
