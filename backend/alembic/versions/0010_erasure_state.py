"""0010 erasure state — legal_hold flag + expanded request states (DPDP Stage 1)

Revision ID: 0010_erasure_state
Revises: 0009_consent_candidate_subject
Create Date: 2026-06-28

Stage 1 of the DPDP erasure engine. Adds the first-class `legal_hold` flag and
expands the dpdp_requests status CHECK to the full state machine
(pending → approved → processing → completed, plus rejected and legal_hold).
Additive + CHECK-widening only; existing rows (pending/completed/…) stay valid.
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_erasure_state'
down_revision = '0009_consent_candidate_subject'
branch_labels = None
depends_on = None

SCHEMA = 'shared'
_NEW = "status IN ('pending','approved','processing','completed','rejected','legal_hold')"
_OLD = "status IN ('pending','processing','completed','rejected')"


def upgrade() -> None:
    op.add_column('dpdp_requests',
                  sa.Column('legal_hold', sa.Boolean(), nullable=False, server_default=sa.text('false')),
                  schema=SCHEMA)
    op.drop_constraint('ck_dpdp_requests_status', 'dpdp_requests', schema=SCHEMA, type_='check')
    op.create_check_constraint('ck_dpdp_requests_status', 'dpdp_requests', _NEW, schema=SCHEMA)


def downgrade() -> None:
    # Only valid if no rows use the new states (approved/legal_hold).
    op.drop_constraint('ck_dpdp_requests_status', 'dpdp_requests', schema=SCHEMA, type_='check')
    op.create_check_constraint('ck_dpdp_requests_status', 'dpdp_requests', _OLD, schema=SCHEMA)
    op.drop_column('dpdp_requests', 'legal_hold', schema=SCHEMA)
