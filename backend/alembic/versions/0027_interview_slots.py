"""0027 interview scheduling depth — slots + rescheduled status + ics bookkeeping (B.8)

Revision ID: 0027_interview_slots
Revises: 0026_aptitude_tests
Create Date: 2026-07-04

- staffing.interview_slots: proposed time slots (>=3 per proposal round, one chosen).
  Normal-DML (not append-only, not in the REVOKE list).
- interviews.status CHECK widened with 'rescheduled' ONLY — no_show already exists
  (0013). Additive; no data migration.
- interviews += ics_sequence (RFC 5545 SEQUENCE, bumped per reschedule so calendar
  clients treat the new .ics as an update) and status_reason (no-show reason —
  `feedback` is client feedback, the wrong container).

Downgrade: best-effort — maps 'rescheduled' rows back to 'scheduled' before
restoring the old CHECK; drops the new columns + table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0027_interview_slots'
down_revision = '0026_aptitude_tests'
branch_labels = None
depends_on = None

S = 'staffing'
OLD = "status IN ('scheduled','completed','cancelled','no_show')"
NEW = "status IN ('scheduled','completed','cancelled','no_show','rescheduled')"


def upgrade() -> None:
    op.create_table(
        'interview_slots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('interview_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.interviews.id'), nullable=False),
        sa.Column('proposed_by', UUID(as_uuid=True), nullable=True),
        sa.Column('slot_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('slot_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('chosen', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING','ACADEMY','CONSULTING')",
                           name='ck_interview_slots_business_unit'),
        sa.CheckConstraint('slot_end > slot_start', name='ck_interview_slots_order'),
        schema=S,
    )
    op.create_index('ix_interview_slots_interview_id', 'interview_slots',
                    ['interview_id'], schema=S)

    op.drop_constraint('ck_interviews_status', 'interviews', schema=S, type_='check')
    op.create_check_constraint('ck_interviews_status', 'interviews', NEW, schema=S)
    op.add_column('interviews', sa.Column('ics_sequence', sa.Integer(), nullable=False,
                                          server_default=sa.text('0')), schema=S)
    op.add_column('interviews', sa.Column('status_reason', sa.Text(), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column('interviews', 'status_reason', schema=S)
    op.drop_column('interviews', 'ics_sequence', schema=S)
    op.execute(f"UPDATE {S}.interviews SET status = 'scheduled' WHERE status = 'rescheduled'")
    op.drop_constraint('ck_interviews_status', 'interviews', schema=S, type_='check')
    op.create_check_constraint('ck_interviews_status', 'interviews', OLD, schema=S)
    op.drop_index('ix_interview_slots_interview_id', table_name='interview_slots', schema=S)
    op.drop_table('interview_slots', schema=S)
