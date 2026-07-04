"""0025 internal evaluations — R1 (aptitude) / R2 (technical) records (B.6)

Revision ID: 0025_internal_evaluations
Revises: 0024_pipeline_stages
Create Date: 2026-07-04

First-class evaluation records (evaluator, result, notes, per round) driving the
B.5 aptitude_*/internal_* transitions THROUGH pipeline.transition() — the row is
persisted in the same txn as the transition, so an illegal transition rolls the
record back too.

Normal business table: sps_app keeps full DML — deliberately NOT in the
bootstrap append-only REVOKE list. Additive/reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0025_internal_evaluations'
down_revision = '0024_pipeline_stages'
branch_labels = None
depends_on = None

S = 'staffing'


def upgrade() -> None:
    op.create_table(
        'internal_evaluations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', UUID(as_uuid=True), nullable=False),
        sa.Column('round', sa.Integer(), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('evaluator_id', UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint('round IN (1, 2)', name='ck_internal_evals_round'),
        sa.CheckConstraint("result IN ('pass','fail')", name='ck_internal_evals_result'),
        schema=S,
    )
    op.create_index('ix_internal_evals_application_round', 'internal_evaluations',
                    ['application_id', 'round'], schema=S)


def downgrade() -> None:
    op.drop_index('ix_internal_evals_application_round',
                  table_name='internal_evaluations', schema=S)
    op.drop_table('internal_evaluations', schema=S)
