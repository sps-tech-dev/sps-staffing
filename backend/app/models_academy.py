"""Academy vertical models (A1) — `academy` schema, two-axis scoped.

courses · cohorts · students · enrollments · attendance · assignments ·
assignment_submissions · certificates · payments. Every table carries the
TwoAxisMixin columns; business_unit_id is 'ACADEMY'. Student PII reuses the
candidate treatment (EncryptedStr + blind index). students.user_id reuses the
F3a linkage (soft-ref to shared.users; A3 auto-links at registration).
"""
from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .crypto import EncryptedStr
from .mixins import TwoAxisMixin, bu_check

SCHEMA = "academy"


class Course(TwoAxisMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        bu_check("courses"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_courses_tenant_slug"),
        sa.Index("ix_courses_tenant", "tenant_id"),
        {"schema": SCHEMA},
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    syllabus: Mapped[str | None] = mapped_column(sa.Text)
    level: Mapped[str | None] = mapped_column(sa.Text)
    duration_weeks: Mapped[int | None] = mapped_column(sa.Integer)
    fee: Mapped[float] = mapped_column(sa.Numeric, nullable=False, server_default=sa.text("50000"))
    currency: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'INR'"))
    is_published: Mapped[bool] = mapped_column(sa.Boolean, nullable=False,
                                               server_default=sa.text("false"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'draft'"))


class Cohort(TwoAxisMixin, Base):
    __tablename__ = "cohorts"
    __table_args__ = (
        bu_check("cohorts"),
        sa.CheckConstraint("mode IN ('online','offline','hybrid')", name="ck_cohorts_mode"),
        sa.CheckConstraint("status IN ('planned','open','running','completed','cancelled')",
                           name="ck_cohorts_status"),
        sa.Index("ix_cohorts_course", "course_id"),
        {"schema": SCHEMA},
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.courses.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    start_date: Mapped[datetime.date | None] = mapped_column(sa.Date)
    end_date: Mapped[datetime.date | None] = mapped_column(sa.Date)
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # soft-ref shared.users
    capacity: Mapped[int | None] = mapped_column(sa.Integer)
    mode: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'online'"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'planned'"))


class Student(TwoAxisMixin, Base):
    # PII (Part 10) mirrors candidates: phone_enc/pan_enc are envelope-encrypted
    # (deferred → not decrypted on list loads); *_bidx are HMAC blind indexes for
    # exact-match/dedup. user_id = the F3a linkage (soft-ref; A3 auto-links).
    __tablename__ = "students"
    __table_args__ = (
        bu_check("students"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_students_tenant_email"),
        sa.UniqueConstraint("tenant_id", "phone_bidx", name="uq_students_tenant_phone_bidx"),
        sa.UniqueConstraint("tenant_id", "student_id", name="uq_students_tenant_student_id"),
        sa.Index("ix_students_tenant", "tenant_id"),
        sa.Index("ix_students_user_id", "user_id"),
        {"schema": SCHEMA},
    )
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone_enc: Mapped[str | None] = mapped_column(EncryptedStr, deferred=True)
    phone_bidx: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    pan_enc: Mapped[str | None] = mapped_column(EncryptedStr, deferred=True)
    pan_bidx: Mapped[bytes | None] = mapped_column(sa.LargeBinary)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    search_doc: Mapped[str | None] = mapped_column(TSVECTOR)
    source: Mapped[str | None] = mapped_column(sa.Text)
    # A3: the student's OWN credential (argon2) — academy is a SEPARATE auth system,
    # NOT shared.users. Set at registration; the academy login verifies against it.
    password_hash: Mapped[str | None] = mapped_column(sa.Text)
    # A3 registration/identity fields — college identity is PLAINTEXT (not PII in
    # the DPDP sense; it's the enrolment identity). id_card_s3_key = a private
    # document (like resumes) deleted on erasure. guardian_* for the under-18 branch.
    student_id: Mapped[str | None] = mapped_column(sa.Text)
    college_name: Mapped[str | None] = mapped_column(sa.Text)
    course_degree: Mapped[str | None] = mapped_column(sa.Text)
    year_of_study: Mapped[str | None] = mapped_column(sa.Text)
    date_of_birth: Mapped["datetime.date | None"] = mapped_column(sa.Date)
    id_card_s3_key: Mapped[str | None] = mapped_column(sa.Text)
    guardian_name: Mapped[str | None] = mapped_column(sa.Text)
    guardian_consent: Mapped[bool | None] = mapped_column(sa.Boolean)
    # A3 consent = Option A: the DPDP consent lives in the canonical shared.consents
    # ledger (subject_student_id soft-ref), NOT on this row. guardian_consent above
    # records WHO consented for a minor.


class Enrollment(TwoAxisMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        bu_check("enrollments"),
        sa.CheckConstraint(
            "status IN ('applied','tested','offered','active','completed','dropped','cancelled')",
            name="ck_enrollments_status"),
        sa.CheckConstraint("payment_status IN ('pending','paid','waived','refunded')",
                           name="ck_enrollments_payment_status"),
        sa.UniqueConstraint("cohort_id", "student_id", name="uq_enrollments_cohort_student"),
        sa.Index("ix_enrollments_student", "student_id"),
        sa.Index("ix_enrollments_cohort", "cohort_id"),
        {"schema": SCHEMA},
    )
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.cohorts.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.students.id"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.courses.id"), nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # soft-ref; A4
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'applied'"))
    aptitude_score: Mapped[float | None] = mapped_column(sa.Numeric)
    discount_percent: Mapped[float | None] = mapped_column(sa.Numeric)
    final_fee: Mapped[float | None] = mapped_column(sa.Numeric)
    payment_status: Mapped[str] = mapped_column(sa.Text, nullable=False,
                                                server_default=sa.text("'pending'"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    enrolled_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))


class Attendance(TwoAxisMixin, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        bu_check("attendance"),
        sa.UniqueConstraint("cohort_id", "student_id", "session_date",
                            name="uq_attendance_cohort_student_date"),
        {"schema": SCHEMA},
    )
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.cohorts.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.students.id"), nullable=False)
    session_date: Mapped[datetime.date] = mapped_column(sa.Date, nullable=False)
    present: Mapped[bool] = mapped_column(sa.Boolean, nullable=False,
                                          server_default=sa.text("false"))


class Assignment(TwoAxisMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        bu_check("assignments"),
        sa.Index("ix_assignments_cohort", "cohort_id"),
        {"schema": SCHEMA},
    )
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.cohorts.id"), nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    due_date: Mapped[datetime.date | None] = mapped_column(sa.Date)
    max_score: Mapped[float | None] = mapped_column(sa.Numeric)


class AssignmentSubmission(TwoAxisMixin, Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        bu_check("assignment_submissions"),
        sa.UniqueConstraint("assignment_id", "student_id",
                            name="uq_assignment_submissions_assignment_student"),
        sa.Index("ix_assignment_submissions_assignment", "assignment_id"),
        {"schema": SCHEMA},
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.assignments.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.students.id"), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(sa.Text)
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(sa.Numeric)
    feedback: Mapped[str | None] = mapped_column(sa.Text)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # soft-ref shared.users
    graded_at: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime(timezone=True))


class Certificate(TwoAxisMixin, Base):
    __tablename__ = "certificates"
    __table_args__ = (
        bu_check("certificates"),
        sa.UniqueConstraint("serial", name="uq_certificates_serial"),
        {"schema": SCHEMA},
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.students.id"), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.courses.id"), nullable=False)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.enrollments.id"), nullable=False)
    serial: Mapped[str] = mapped_column(sa.Text, nullable=False)
    issued_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(sa.Text)


class Payment(TwoAxisMixin, Base):
    # A6 wires the stub-pay lifecycle; Part-D swaps in Razorpay (order + webhook).
    __tablename__ = "payments"
    __table_args__ = (
        bu_check("payments"),
        sa.CheckConstraint("status IN ('created','paid','failed','refunded')",
                           name="ck_payments_status"),
        sa.Index("ix_payments_enrollment", "enrollment_id"),
        {"schema": SCHEMA},
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.enrollments.id"), nullable=False)
    amount: Mapped[float] = mapped_column(sa.Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'INR'"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'created'"))
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=sa.text("'stub'"))
    provider_ref: Mapped[str | None] = mapped_column(sa.Text)
