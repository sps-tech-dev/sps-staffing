"""0035 generalize staffing.tests to be vertical-agnostic (A4 part 1)

Revision ID: 0035_tests_vertical_agnostic
Revises: 0034_academy_student_reg
Create Date: 2026-07-05

A4 Part-0 (approved): the enrollment IS the academy application. An academy
aptitude test belongs to a STUDENT taking a test for an ENROLLMENT — neither a
staffing application nor a staffing candidate. staffing.tests currently pins
application_id (→ staffing.applications) and candidate_id (→ staffing.candidates)
NOT NULL, which blocks an academy test.

This migration makes the tests table vertical-agnostic WITHOUT forking an
academy.tests table (reuse mandate): the take flow (/take/{token}) stays
identity-agnostic; only issue + the post-grade callback branch on
business_unit_id. IDENTITY/DISCRIMINATOR ONLY — the 60Q/60min config is the
later engine-extension prompt, NOT this migration.

Changes (mirrors the consent three-way pattern):
  - application_id, candidate_id → NULLABLE (keep their within-schema FKs).
  - add enrollment_id, student_id — nullable uuid SOFT-REFS (NO cross-schema FK,
    matching enrollments.application_id / trainer_id / graded_by convention).
  - CHECK: EXACTLY ONE identity pairing is set
      staffing: application_id + candidate_id set, enrollment_id + student_id null
      academy:  enrollment_id + student_id set, application_id + candidate_id null
  - index the two new columns.

NO BACKFILL NEEDED: every existing staffing.tests row already has application_id +
candidate_id set and the two new columns null → all satisfy the staffing branch
of the CHECK. Additive; NOT in the REVOKE list. Reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0035_tests_vertical_agnostic'
down_revision = '0034_academy_student_reg'
branch_labels = None
depends_on = None

S = 'staffing'

_ONE_PAIRING = (
    "(application_id IS NOT NULL AND candidate_id IS NOT NULL "
    " AND enrollment_id IS NULL AND student_id IS NULL) "
    "OR "
    "(enrollment_id IS NOT NULL AND student_id IS NOT NULL "
    " AND application_id IS NULL AND candidate_id IS NULL)"
)


def upgrade() -> None:
    # staffing FKs become nullable (they keep the FK — a nullable FK is valid;
    # the academy branch leaves them NULL, the staffing branch sets them)
    op.alter_column('tests', 'application_id', existing_type=UUID(as_uuid=True),
                    nullable=True, schema=S)
    op.alter_column('tests', 'candidate_id', existing_type=UUID(as_uuid=True),
                    nullable=True, schema=S)
    # academy soft-refs (no cross-schema FK — convention)
    op.add_column('tests', sa.Column('enrollment_id', UUID(as_uuid=True), nullable=True), schema=S)
    op.add_column('tests', sa.Column('student_id', UUID(as_uuid=True), nullable=True), schema=S)
    op.create_check_constraint('ck_tests_one_identity', 'tests', _ONE_PAIRING, schema=S)
    op.create_index('ix_tests_enrollment_id', 'tests', ['enrollment_id'], schema=S)
    op.create_index('ix_tests_student_id', 'tests', ['student_id'], schema=S)


def downgrade() -> None:
    # Reversible ASSUMPTION: down runs only BEFORE any academy test rows exist
    # (this migration ships ahead of the academy issue endpoint). All rows are
    # therefore staffing rows with application_id + candidate_id set, so re-adding
    # NOT NULL is safe.
    op.drop_index('ix_tests_student_id', table_name='tests', schema=S)
    op.drop_index('ix_tests_enrollment_id', table_name='tests', schema=S)
    op.drop_constraint('ck_tests_one_identity', 'tests', schema=S, type_='check')
    op.drop_column('tests', 'student_id', schema=S)
    op.drop_column('tests', 'enrollment_id', schema=S)
    op.alter_column('tests', 'candidate_id', existing_type=UUID(as_uuid=True),
                    nullable=False, schema=S)
    op.alter_column('tests', 'application_id', existing_type=UUID(as_uuid=True),
                    nullable=False, schema=S)
