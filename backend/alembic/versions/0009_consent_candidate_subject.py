"""0009 consent candidate subject — allow consent against a candidate (registration)

Revision ID: 0009_consent_candidate_subject
Revises: 0008_candidate_pii_contract
Create Date: 2026-06-28

Public candidate registration records DPDP consent at the point of collection, but
the registrant has no user account yet. Generalize shared.consents so the subject
is EITHER a user (DPDP self-service) OR a candidate (registration):
- add subject_candidate_id (UUID, nullable; soft ref — no cross-schema FK to the
  staffing vertical),
- relax subject_user_id to NULLable,
- CHECK exactly one subject is set.
Existing rows (subject_user_id set) satisfy the new CHECK. Additive/relaxing only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_consent_candidate_subject'
down_revision = '0008_candidate_pii_contract'
branch_labels = None
depends_on = None

SCHEMA = 'shared'


def upgrade() -> None:
    op.add_column('consents', sa.Column('subject_candidate_id', sa.UUID(), nullable=True), schema=SCHEMA)
    op.alter_column('consents', 'subject_user_id', existing_type=sa.UUID(), nullable=True, schema=SCHEMA)
    op.create_check_constraint(
        'ck_consents_one_subject', 'consents',
        'num_nonnulls(subject_user_id, subject_candidate_id) = 1', schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint('ck_consents_one_subject', 'consents', schema=SCHEMA, type_='check')
    # Restore NOT NULL (only valid if no candidate-subject rows exist).
    op.alter_column('consents', 'subject_user_id', existing_type=sa.UUID(), nullable=False, schema=SCHEMA)
    op.drop_column('consents', 'subject_candidate_id', schema=SCHEMA)
