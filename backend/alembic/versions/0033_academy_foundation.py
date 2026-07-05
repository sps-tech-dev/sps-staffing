"""0033 Academy foundation (A1)

Revision ID: 0033_academy_foundation
Revises: 0032_candidate_user_link
Create Date: 2026-07-05

The whole `academy` schema (schema itself created empty by 0001): courses,
cohorts, students, enrollments, attendance, assignments, assignment_submissions,
certificates, payments. All two-axis tagged (tenant_id + business_unit_id CHECK
'STAFFING'/'ACADEMY'/'CONSULTING'; academy rows carry 'ACADEMY'), soft-delete,
created_at/updated_at — matching every staffing vertical table (TwoAxisMixin).

STUDENT PII mirrors candidates: phone_enc/pan_enc (bytea AES-256-GCM ciphertext)
+ phone_bidx/pan_bidx (bytea HMAC blind index) + email CITEXT + search_doc
TSVECTOR. UNIQUE(tenant_id,email) + UNIQUE(tenant_id,phone_bidx) dedup (NULL bidx
exempt by SQL null semantics).

STUDENT↔LOGIN linkage reuses F3a exactly: students.user_id uuid NULL — a SOFT REF
to shared.users (NO cross-schema FK, matching jobs.owner_user_id /
candidates.user_id). NULL valid; auto-link at registration lands in A3.

CROSS-SCHEMA refs (trainer_id, students.user_id, graded_by, enrollments.
application_id) are soft-refs — NO FK — per the codebase convention. WITHIN-schema
refs (academy.* → academy.*) ARE real FKs.

All academy tables are NORMAL-DML (full CRUD for sps_app) — NOT in the append-only
REVOKE list (bootstrap REVOKEs only shared.audit_logs / shared.consents /
staffing.candidate_timeline).

Seeds the 8 scaffolded courses via app.academy_seed.seed_courses (idempotent,
single source of truth shared with the test fixture — E2E-3 reproducibility).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, TSVECTOR, UUID

from app.academy_seed import seed_courses

revision = '0033_academy_foundation'
down_revision = '0032_candidate_user_link'
branch_labels = None
depends_on = None

S = 'academy'
BU = "business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')"


def _axis():
    """The TwoAxisMixin columns every vertical table carries."""
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False,
                  server_default=sa.text("'ACADEMY'")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ── courses ──
    op.create_table(
        'courses', *_axis(),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('syllabus', sa.Text(), nullable=True),
        sa.Column('level', sa.Text(), nullable=True),
        sa.Column('duration_weeks', sa.Integer(), nullable=True),
        sa.Column('fee', sa.Numeric(), nullable=False, server_default=sa.text('50000')),
        sa.Column('currency', sa.Text(), nullable=False, server_default=sa.text("'INR'")),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.CheckConstraint(BU, name='ck_courses_business_unit'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_courses_tenant_slug'),
        schema=S,
    )
    op.create_index('ix_courses_tenant', 'courses', ['tenant_id'], schema=S)

    # ── cohorts ──
    op.create_table(
        'cohorts', *_axis(),
        sa.Column('course_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.courses.id'),
                  nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('trainer_id', UUID(as_uuid=True), nullable=True),   # soft-ref shared.users
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('mode', sa.Text(), nullable=False, server_default=sa.text("'online'")),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'planned'")),
        sa.CheckConstraint(BU, name='ck_cohorts_business_unit'),
        sa.CheckConstraint("mode IN ('online','offline','hybrid')", name='ck_cohorts_mode'),
        sa.CheckConstraint("status IN ('planned','open','running','completed','cancelled')",
                           name='ck_cohorts_status'),
        schema=S,
    )
    op.create_index('ix_cohorts_course', 'cohorts', ['course_id'], schema=S)

    # ── students (PII like candidates) ──
    op.create_table(
        'students', *_axis(),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('email', CITEXT(), nullable=True),
        sa.Column('phone_enc', sa.LargeBinary(), nullable=True),
        sa.Column('phone_bidx', sa.LargeBinary(), nullable=True),
        sa.Column('pan_enc', sa.LargeBinary(), nullable=True),
        sa.Column('pan_bidx', sa.LargeBinary(), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),      # F3a soft-ref (A3 auto-links)
        sa.Column('search_doc', TSVECTOR(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.CheckConstraint(BU, name='ck_students_business_unit'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_students_tenant_email'),
        sa.UniqueConstraint('tenant_id', 'phone_bidx', name='uq_students_tenant_phone_bidx'),
        schema=S,
    )
    op.create_index('ix_students_tenant', 'students', ['tenant_id'], schema=S)
    op.create_index('ix_students_user_id', 'students', ['user_id'], schema=S)

    # ── enrollments (the apply→test→pay→enrol chain) ──
    op.create_table(
        'enrollments', *_axis(),
        sa.Column('cohort_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.cohorts.id'),
                  nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.students.id'),
                  nullable=False),
        sa.Column('course_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.courses.id'),
                  nullable=False),
        sa.Column('application_id', UUID(as_uuid=True), nullable=True),  # soft-ref, A4 wires the test
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'applied'")),
        sa.Column('aptitude_score', sa.Numeric(), nullable=True),
        sa.Column('discount_percent', sa.Numeric(), nullable=True),
        sa.Column('final_fee', sa.Numeric(), nullable=True),
        sa.Column('payment_status', sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('payment_id', UUID(as_uuid=True), nullable=True),      # soft-ref academy.payments
        sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU, name='ck_enrollments_business_unit'),
        sa.CheckConstraint(
            "status IN ('applied','tested','offered','active','completed','dropped','cancelled')",
            name='ck_enrollments_status'),
        sa.CheckConstraint("payment_status IN ('pending','paid','waived','refunded')",
                           name='ck_enrollments_payment_status'),
        sa.UniqueConstraint('cohort_id', 'student_id', name='uq_enrollments_cohort_student'),
        schema=S,
    )
    op.create_index('ix_enrollments_student', 'enrollments', ['student_id'], schema=S)
    op.create_index('ix_enrollments_cohort', 'enrollments', ['cohort_id'], schema=S)

    # ── attendance ──
    op.create_table(
        'attendance', *_axis(),
        sa.Column('cohort_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.cohorts.id'),
                  nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.students.id'),
                  nullable=False),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('present', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.CheckConstraint(BU, name='ck_attendance_business_unit'),
        sa.UniqueConstraint('cohort_id', 'student_id', 'session_date',
                            name='uq_attendance_cohort_student_date'),
        schema=S,
    )

    # ── assignments ──
    op.create_table(
        'assignments', *_axis(),
        sa.Column('cohort_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.cohorts.id'),
                  nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('max_score', sa.Numeric(), nullable=True),
        sa.CheckConstraint(BU, name='ck_assignments_business_unit'),
        schema=S,
    )
    op.create_index('ix_assignments_cohort', 'assignments', ['cohort_id'], schema=S)

    # ── assignment_submissions ──
    op.create_table(
        'assignment_submissions', *_axis(),
        sa.Column('assignment_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.assignments.id'),
                  nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.students.id'),
                  nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('score', sa.Numeric(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('graded_by', UUID(as_uuid=True), nullable=True),   # soft-ref shared.users
        sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU, name='ck_assignment_submissions_business_unit'),
        sa.UniqueConstraint('assignment_id', 'student_id',
                            name='uq_assignment_submissions_assignment_student'),
        schema=S,
    )
    op.create_index('ix_assignment_submissions_assignment', 'assignment_submissions',
                    ['assignment_id'], schema=S)

    # ── certificates ──
    op.create_table(
        'certificates', *_axis(),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.students.id'),
                  nullable=False),
        sa.Column('course_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.courses.id'),
                  nullable=False),
        sa.Column('enrollment_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.enrollments.id'),
                  nullable=False),
        sa.Column('serial', sa.Text(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=True),
        sa.CheckConstraint(BU, name='ck_certificates_business_unit'),
        sa.UniqueConstraint('serial', name='uq_certificates_serial'),
        schema=S,
    )

    # ── payments (stub now; A6 wires stub-pay; Part-D swaps Razorpay) ──
    op.create_table(
        'payments', *_axis(),
        sa.Column('enrollment_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.enrollments.id'),
                  nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('currency', sa.Text(), nullable=False, server_default=sa.text("'INR'")),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column('provider', sa.Text(), nullable=False, server_default=sa.text("'stub'")),
        sa.Column('provider_ref', sa.Text(), nullable=True),
        sa.CheckConstraint(BU, name='ck_payments_business_unit'),
        sa.CheckConstraint("status IN ('created','paid','failed','refunded')",
                           name='ck_payments_status'),
        schema=S,
    )
    op.create_index('ix_payments_enrollment', 'payments', ['enrollment_id'], schema=S)

    # ── seed the 8 courses for the owner tenant (idempotent, shared source) ──
    conn = op.get_bind()
    tenant_id = conn.execute(sa.text(
        "SELECT id FROM shared.tenants WHERE code = 'SPS001'")).scalar_one_or_none()
    if tenant_id is not None:
        seed_courses(conn, tenant_id)


def downgrade() -> None:
    for tbl in ('payments', 'certificates', 'assignment_submissions', 'assignments',
                'attendance', 'enrollments', 'students', 'cohorts', 'courses'):
        op.drop_table(tbl, schema=S)
