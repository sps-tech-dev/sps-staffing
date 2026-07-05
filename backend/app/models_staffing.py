"""Staffing vertical models (Part 5) — `staffing` schema, two-axis scoped.

clients · jobs · candidates · applications. Every table carries the TwoAxisMixin
columns (id, tenant_id, business_unit_id TEXT+CHECK, created_at, updated_at,
deleted_at). business_unit_id is 'STAFFING' for these rows.
"""
from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .crypto import EncryptedStr
from .mixins import TenantScopedMixin, TwoAxisMixin, bu_check

SCHEMA = "staffing"

# Pipeline state machine (Part 5, full vocabulary since B.5 / migration 0024).
# Transitions are enforced EXCLUSIVELY by app/pipeline.py; this CHECK bounds values.
APPLICATION_STAGES = (
    "applied", "screening", "aptitude_test", "aptitude_passed", "aptitude_failed",
    "internal_interview", "internal_passed", "rtr_pending", "submitted_to_client",
    "client_round_1", "client_round_2", "client_round_3", "offer", "offer_accepted",
    "joined", "guarantee", "invoiced", "paid", "withdrawn", "dropped", "on_hold",
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
    # B.9 (0028): CLIENT-level placement-fee override. Resolution order:
    # per-invoice override → client.fee_percent → global default 15.
    fee_percent: Mapped[float] = mapped_column(sa.Numeric, nullable=False, server_default=sa.text("15"))


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
        sa.Index("ix_candidates_user_id", "user_id"),
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
    # F3a (0032): EXPLICIT link to the candidate's portal login (soft ref to
    # shared.users, matching jobs.owner_user_id — no cross-schema FK). NULL is
    # valid (sourced candidates have no portal). Set at registration when the
    # registrant already has a candidate login; carried through B.3 merges
    # (both-different-logins → conflict FLAGGED, never silently dropped).
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
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
    # Server-side extracted resume text (B.1, migration 0020). Contains PII — the
    # erasure anonymize path nulls it together with resume_s3_key. Feeds B.4 search.
    resume_text: Mapped[str | None] = mapped_column(sa.Text)
    resume_uploaded_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(sa.Text)
    search_doc: Mapped[str | None] = mapped_column(TSVECTOR)  # Part 20 FTS (trigger added later)


class CandidateTimeline(Base):
    # EXCEPTION (decision B, like shared.audit_logs): bigserial PK, APPEND-ONLY,
    # no mixin/soft-delete. sps_app has INSERT/SELECT only (bootstrap REVOKE) —
    # never UPDATE/DELETE this table from app code; there is no legal write path
    # other than emit_timeline().
    __tablename__ = "candidate_timeline"
    __table_args__ = (
        sa.Index("ix_candidate_timeline_candidate_occurred", "candidate_id", "occurred_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class CandidateDupReview(Base):
    # Human review queue for FUZZY duplicate suspects (B.3, create-then-flag: the
    # incoming candidate is CREATED first, then flagged here). Normal business
    # table — sps_app keeps full DML (NOT append-only; not in the bootstrap REVOKE).
    __tablename__ = "candidate_dup_reviews"
    __table_args__ = (
        sa.CheckConstraint("match_type IN ('exact','fuzzy')", name="ck_dup_reviews_match_type"),
        sa.CheckConstraint("status IN ('pending','merged','dismissed')", name="ck_dup_reviews_status"),
        sa.Index("ix_dup_reviews_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)          # incoming/new
    matched_candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # suspected match
    match_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    score: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    incoming_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'pending'"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


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
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'applied'"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # recruiter (internal)
    # B.5 (0024): optimistic lock + hold/drop bookkeeping + RTR submit-gate.
    # stage is written ONLY by app/pipeline.py (transition/adopt_stage_on_merge).
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("1"))
    hold_reason: Mapped[str | None] = mapped_column(sa.Text)
    drop_reason: Mapped[str | None] = mapped_column(sa.Text)
    hold_prior_stage: Mapped[str | None] = mapped_column(sa.Text)
    rtr_consent_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rtr_consent_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class InternalEvaluation(Base):
    # B.6: R1 (aptitude) / R2 (internal technical) evaluation records. First-class
    # business data (queried by recruiters) — NOT derived from timeline payloads.
    # Normal DML table for sps_app (not append-only). Stage effects go EXCLUSIVELY
    # through pipeline.transition() in the same txn as this row.
    __tablename__ = "internal_evaluations"
    __table_args__ = (
        sa.CheckConstraint("round IN (1, 2)", name="ck_internal_evals_round"),
        sa.CheckConstraint("result IN ('pass','fail')", name="ck_internal_evals_result"),
        sa.Index("ix_internal_evals_application_round", "application_id", "round"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    round: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    result: Mapped[str] = mapped_column(sa.Text, nullable=False)
    evaluator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


# ── B.7 aptitude test engine ─────────────────────────────────────
QUESTION_DIFFICULTIES = ("easy", "medium", "hard")
_DIFF_SQL = ", ".join(f"'{d}'" for d in QUESTION_DIFFICULTIES)
TEST_STATUSES = ("issued", "started", "submitted", "expired")
_TEST_SQL = ", ".join(f"'{s}'" for s in TEST_STATUSES)


class QuestionBank(TwoAxisMixin, Base):
    __tablename__ = "question_banks"
    __table_args__ = (
        bu_check("question_banks"),
        sa.Index("ix_question_banks_tenant_bu", "tenant_id", "business_unit_id"),
        {"schema": SCHEMA},
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    category: Mapped[str | None] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))


class Question(TwoAxisMixin, Base):
    # correct_index NEVER leaves the server: the take-test fetch returns stems +
    # shuffled options only; grading runs against the FROZEN copy in tests.served_questions.
    __tablename__ = "questions"
    __table_args__ = (
        bu_check("questions"),
        sa.CheckConstraint(f"difficulty IN ({_DIFF_SQL})", name="ck_questions_difficulty"),
        sa.Index("ix_questions_bank_id", "bank_id"),
        {"schema": SCHEMA},
    )
    bank_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.question_banks.id"), nullable=False
    )
    category: Mapped[str | None] = mapped_column(sa.Text)
    difficulty: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'medium'"))
    stem: Mapped[str] = mapped_column(sa.Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))


class Test(TwoAxisMixin, Base):
    # One aptitude attempt. link_token_hash = SHA-256 of the one-time token (raw
    # token shown once at issue, never stored). served_questions is the FROZEN
    # paper (ids + shuffled options + correct answer captured at freeze) — grading
    # never re-queries the bank, so later edits can't change a taken test.
    __tablename__ = "tests"
    __table_args__ = (
        bu_check("tests"),
        sa.CheckConstraint(f"status IN ({_TEST_SQL})", name="ck_tests_status"),
        # A4 (0035): vertical-agnostic identity — EXACTLY ONE pairing is set,
        # staffing (application+candidate) OR academy (enrollment+student).
        sa.CheckConstraint(
            "(application_id IS NOT NULL AND candidate_id IS NOT NULL "
            " AND enrollment_id IS NULL AND student_id IS NULL) "
            "OR (enrollment_id IS NOT NULL AND student_id IS NOT NULL "
            " AND application_id IS NULL AND candidate_id IS NULL)",
            name="ck_tests_one_identity"),
        sa.UniqueConstraint("link_token_hash", name="uq_tests_link_token_hash"),
        sa.Index("ix_tests_application_id", "application_id"),
        sa.Index("ix_tests_enrollment_id", "enrollment_id"),
        sa.Index("ix_tests_student_id", "student_id"),
        {"schema": SCHEMA},
    )
    # staffing identity (within-schema FKs, now NULLABLE for the academy branch)
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"))
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.candidates.id"))
    # academy identity (soft-refs — no cross-schema FK; A4 issue endpoint sets these)
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    student_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    link_token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    valid_until: Mapped[datetime.datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'issued'"))
    attempt_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("1"))
    served_questions: Mapped[list | None] = mapped_column(JSONB)
    started_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(sa.Numeric)
    passed: Mapped[bool | None] = mapped_column(sa.Boolean)
    proctor_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))


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
INTERVIEW_STATUSES = ("scheduled", "completed", "cancelled", "no_show", "rescheduled")
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
    # B.8 (0027): RFC 5545 SEQUENCE (bumped per reschedule) + no-show/reschedule reason
    ics_sequence: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    status_reason: Mapped[str | None] = mapped_column(sa.Text)


class InterviewSlot(Base):
    # B.8: proposed time slots (>=3 per proposal round; exactly one becomes chosen).
    # Normal-DML; no soft-delete/timestamps mixin — a slot round is replaced wholesale
    # on re-proposal (reschedule), and slot history that matters lives in audit/timeline.
    __tablename__ = "interview_slots"
    __table_args__ = (
        sa.CheckConstraint("business_unit_id IN ('STAFFING','ACADEMY','CONSULTING')",
                           name="ck_interview_slots_business_unit"),
        sa.CheckConstraint("slot_end > slot_start", name="ck_interview_slots_order"),
        sa.Index("ix_interview_slots_interview_id", "interview_id"),
        {"schema": SCHEMA},
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=sa.text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_unit_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.interviews.id"), nullable=False
    )
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    slot_start: Mapped[datetime.datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    slot_end: Mapped[datetime.datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    chosen: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


PLACEMENT_STATUSES = ("active", "in_guarantee", "cleared", "breached", "replaced")
_PLC_SQL = ", ".join(f"'{s}'" for s in PLACEMENT_STATUSES)


class Placement(TwoAxisMixin, Base):
    # B.9: the revenue object. offered_ctc = ANNUAL CTC (INR), founder-confirmed
    # (Part 0-FEE): fee = annual_ctc × resolved fee_percent / 100. `status` is the
    # MATERIALIZED state (active → cleared|breached → replaced); the guarantee
    # position is always DERIVABLE from joined_on/guarantee_until on read — the
    # sweep job only materializes; a missed run self-heals on the next pass.
    # ('in_guarantee' is in the CHECK for forward-compat; the code derives it and
    # stores 'active' during the window.)
    __tablename__ = "placements"
    __table_args__ = (
        bu_check("placements"),
        sa.CheckConstraint(f"status IN ({_PLC_SQL})", name="ck_placements_status"),
        sa.CheckConstraint("guarantee_until >= joined_on", name="ck_placements_guarantee_order"),
        sa.Index("ix_placements_application_id", "application_id"),
        sa.Index("ix_placements_guarantee_until", "guarantee_until"),
        {"schema": SCHEMA},
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.applications.id"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.candidates.id"), nullable=False
    )
    recruiter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # commission attribution
    offered_ctc: Mapped[float] = mapped_column(sa.Numeric, nullable=False)      # ANNUAL CTC (INR)
    joined_on: Mapped[datetime.date] = mapped_column(sa.Date, nullable=False)
    guarantee_until: Mapped[datetime.date] = mapped_column(sa.Date, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))
    breach_reason: Mapped[str | None] = mapped_column(sa.Text)
    replacement_for: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.placements.id")
    )  # no-double-fee: a replacement placement raises NO invoice


VENDOR_COMMISSION_STATUSES = ("accrued", "paid", "void")
_VC_SQL = ", ".join(f"'{s}'" for s in VENDOR_COMMISSION_STATUSES)


class VendorContract(TwoAxisMixin, Base):
    # B.13: contract base commission %. The contract valid AT placement.joined_on
    # governs (rate locks at accrual — see VendorCommission).
    __tablename__ = "vendor_contracts"
    __table_args__ = (
        bu_check("vendor_contracts"),
        sa.CheckConstraint("status IN ('active','expired','terminated')",
                           name="ck_vendor_contracts_status"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until >= valid_from",
                           name="ck_vendor_contracts_window"),
        sa.Index("ix_vendor_contracts_vendor", "vendor_id"),
        {"schema": SCHEMA},
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False)
    base_commission_percent: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    valid_from: Mapped[datetime.date] = mapped_column(sa.Date, nullable=False)
    valid_until: Mapped[datetime.date | None] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'active'"))


class VendorClientRate(TwoAxisMixin, Base):
    # B.13: the CLIENT-DYNAMIC level — a vendor x client rate matrix (a table,
    # not a column: N clients per vendor). Beats the contract base; beaten only
    # by a per-placement override.
    __tablename__ = "vendor_client_rates"
    __table_args__ = (
        bu_check("vendor_client_rates"),
        sa.UniqueConstraint("vendor_id", "client_id", name="uq_vendor_client_rates"),
        {"schema": SCHEMA},
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.clients.id"), nullable=False)
    commission_percent: Mapped[float] = mapped_column(sa.Numeric, nullable=False)


class VendorCommission(TwoAxisMixin, Base):
    # B.13: MATERIALIZED commission ledger — the rate LOCK (valid-at-placement-
    # date) requires a persisted row; also carries accrued->paid|void.
    # UNIQUE(placement_id) = one commission per placement, structurally.
    # base_amount = the PLACEMENT FEE (SPS earnings share), never CTC.
    __tablename__ = "vendor_commissions"
    __table_args__ = (
        bu_check("vendor_commissions"),
        sa.CheckConstraint(f"status IN ({_VC_SQL})", name="ck_vendor_commissions_status"),
        sa.UniqueConstraint("placement_id", name="uq_vendor_commissions_placement"),
        sa.Index("ix_vendor_commissions_vendor", "vendor_id"),
        {"schema": SCHEMA},
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.vendors.id"), nullable=False)
    placement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.placements.id"), nullable=False)
    resolved_percent: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    base_amount: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    commission_amount: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'accrued'"))
    void_reason: Mapped[str | None] = mapped_column(sa.Text)
    computed_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


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
    # B.9 (0028): placement linkage + no-double-fee + credit-note STRUCTURE (GST inert)
    placement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.placements.id"))
    is_replacement: Mapped[bool] = mapped_column(sa.Boolean, nullable=False,
                                                 server_default=sa.text("false"))
    credit_note_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # soft self-ref
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
