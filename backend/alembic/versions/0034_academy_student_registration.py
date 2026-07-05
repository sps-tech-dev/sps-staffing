"""0034 Academy student registration + SEPARATE student auth (A3)

Revision ID: 0034_academy_student_reg
Revises: 0033_academy_foundation
Create Date: 2026-07-05

STOP-0 identity decision (approved, Option 1): academy students are a DISTINCT
identity in academy.students with their OWN argon2 password_hash and a SEPARATE
JWT auth system. NO change to shared.USERS — the identity spine does not move.

Consent = Option A (approved): student DPDP consent goes in the canonical
shared.consents ledger via a NEW `subject_student_id` soft-ref (uuid, NO
cross-schema FK — exactly like subject_candidate_id), and the one-subject CHECK
widens to num_nonnulls(user, candidate, student)=1. Guardian consent stays on
the student row (the purpose CHECK is untouched).

academy.students gains: password_hash (credential), the college-identity fields,
the ID-card key, and the under-18 guardian fields. Email uniqueness already
exists (A1 uq_students_tenant_email); student_id uniqueness added here. All
nullable (public form enforces required-ness via validation). Normal-DML — NOT
in the REVOKE list. Additive/reversible. Seeds the two academy notification
templates (idempotent, shared source of truth).
"""
from alembic import op
import sqlalchemy as sa

from app.academy_seed import seed_notification_templates

revision = '0034_academy_student_reg'
down_revision = '0033_academy_foundation'
branch_labels = None
depends_on = None

S = 'academy'


def upgrade() -> None:
    op.add_column('students', sa.Column('password_hash', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('student_id', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('college_name', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('course_degree', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('year_of_study', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('date_of_birth', sa.Date(), nullable=True), schema=S)
    op.add_column('students', sa.Column('id_card_s3_key', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('guardian_name', sa.Text(), nullable=True), schema=S)
    op.add_column('students', sa.Column('guardian_consent', sa.Boolean(), nullable=True), schema=S)
    op.create_unique_constraint('uq_students_tenant_student_id', 'students',
                                ['tenant_id', 'student_id'], schema=S)

    # Option A: student consent in the canonical shared.consents ledger. Add the
    # subject_student_id soft-ref (uuid, no cross-schema FK — like subject_candidate_id)
    # and widen the one-subject CHECK to include it.
    op.add_column('consents', sa.Column('subject_student_id', sa.UUID(), nullable=True),
                  schema='shared')
    op.drop_constraint('ck_consents_one_subject', 'consents', schema='shared', type_='check')
    op.create_check_constraint(
        'ck_consents_one_subject', 'consents',
        'num_nonnulls(subject_user_id, subject_candidate_id, subject_student_id) = 1',
        schema='shared')

    seed_notification_templates(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM shared.notification_templates WHERE code IN "
               "('student_welcome', 'admin_new_student_application')")
    # revert the shared.consents widening
    op.drop_constraint('ck_consents_one_subject', 'consents', schema='shared', type_='check')
    op.create_check_constraint(
        'ck_consents_one_subject', 'consents',
        'num_nonnulls(subject_user_id, subject_candidate_id) = 1', schema='shared')
    op.drop_column('consents', 'subject_student_id', schema='shared')
    op.drop_constraint('uq_students_tenant_student_id', 'students', schema=S, type_='unique')
    for col in ('guardian_consent', 'guardian_name', 'id_card_s3_key', 'date_of_birth',
                'year_of_study', 'course_degree', 'college_name', 'student_id', 'password_hash'):
        op.drop_column('students', col, schema=S)
