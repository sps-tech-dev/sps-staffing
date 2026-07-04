"""0032 candidate↔user linkage (F3a)

Revision ID: 0032_candidate_user_link
Revises: 0031_vendor_depth
Create Date: 2026-07-04

Explicit link (NOT runtime email-matching): candidates.user_id uuid NULL — a
SOFT REF to shared.users, matching the existing cross-schema convention
(jobs.owner_user_id has no FK either; cross-schema FKs are avoided in this
codebase). NULL is valid: staff-created/sourced candidates have no portal login.

Additive/reversible; candidates stays normal-DML (not in the REVOKE list).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0032_candidate_user_link'
down_revision = '0031_vendor_depth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('user_id', UUID(as_uuid=True), nullable=True),
                  schema='staffing')
    op.create_index('ix_candidates_user_id', 'candidates', ['user_id'], schema='staffing')


def downgrade() -> None:
    op.drop_index('ix_candidates_user_id', table_name='candidates', schema='staffing')
    op.drop_column('candidates', 'user_id', schema='staffing')
