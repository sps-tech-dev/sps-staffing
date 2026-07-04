"""0021 candidate timeline — append-only event store (B.2)

Revision ID: 0021_candidate_timeline
Revises: 0020_candidate_resume
Create Date: 2026-07-04

Part 18: immutable chronological history per candidate. Mirrors the audit_logs
shape (decision B): bigserial PK, NO TwoAxisMixin, no updated_at/deleted_at.
Append-only is enforced at the DB level by REVOKE UPDATE/DELETE FROM sps_app in
backend/scripts/bootstrap_app_role.py — the REVOKE must be (re-)run after this
migration because master's default privileges grant sps_app full DML on new tables.

Additive + reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0021_candidate_timeline'
down_revision = '0020_candidate_resume'
branch_labels = None
depends_on = None

S = 'staffing'


def upgrade() -> None:
    op.create_table(
        'candidate_timeline',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('candidate_id', UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('actor_id', UUID(as_uuid=True), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        schema=S,
    )
    op.create_index('ix_candidate_timeline_candidate_occurred', 'candidate_timeline',
                    ['candidate_id', 'occurred_at'], schema=S)


def downgrade() -> None:
    op.drop_index('ix_candidate_timeline_candidate_occurred',
                  table_name='candidate_timeline', schema=S)
    op.drop_table('candidate_timeline', schema=S)
