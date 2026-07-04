"""0028 commercial layer — placements + guarantee + fee override + invoice links (B.9)

Revision ID: 0028_placements
Revises: 0027_interview_slots
Create Date: 2026-07-04

- staffing.placements: the revenue object. offered_ctc is ANNUAL CTC (INR) —
  founder-confirmed (Part 0-FEE); fee = annual_ctc × resolved fee_percent / 100.
  guarantee_until = joined_on + 60d (config). status is the MATERIALIZED state;
  the guarantee position (in_guarantee/clear-able) is always DERIVABLE from the
  dates on read — the sweep job only materializes, it is never the source of truth.
  replacement_for: self-ref for the no-double-fee replacement rule.
- clients.fee_percent numeric NOT NULL DEFAULT 15 — the CLIENT-level fee override.
  Resolution order: per-invoice override → client.fee_percent → global default 15.
- invoices += placement_id (FK), is_replacement (fee-exempt marker),
  credit_note_of (soft self-ref; credit-note STRUCTURE only — GST math stays inert
  per C.3/PENDING B5).

Normal-DML tables (not in the append-only REVOKE list). Additive/reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0028_placements'
down_revision = '0027_interview_slots'
branch_labels = None
depends_on = None

S = 'staffing'


def upgrade() -> None:
    op.create_table(
        'placements',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.applications.id'), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.clients.id'), nullable=True),
        sa.Column('candidate_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.candidates.id'), nullable=False),
        sa.Column('recruiter_id', UUID(as_uuid=True), nullable=True),
        sa.Column('offered_ctc', sa.Numeric(), nullable=False),   # ANNUAL CTC (INR)
        sa.Column('joined_on', sa.Date(), nullable=False),
        sa.Column('guarantee_until', sa.Date(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column('breach_reason', sa.Text(), nullable=True),
        sa.Column('replacement_for', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.placements.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("business_unit_id IN ('STAFFING','ACADEMY','CONSULTING')",
                           name='ck_placements_business_unit'),
        sa.CheckConstraint(
            "status IN ('active','in_guarantee','cleared','breached','replaced')",
            name='ck_placements_status'),
        sa.CheckConstraint('guarantee_until >= joined_on', name='ck_placements_guarantee_order'),
        schema=S,
    )
    op.create_index('ix_placements_application_id', 'placements', ['application_id'], schema=S)
    op.create_index('ix_placements_guarantee_until', 'placements', ['guarantee_until'], schema=S)

    op.add_column('clients', sa.Column('fee_percent', sa.Numeric(), nullable=False,
                                       server_default=sa.text('15')), schema=S)

    op.add_column('invoices', sa.Column('placement_id', UUID(as_uuid=True), nullable=True), schema=S)
    op.create_foreign_key('fk_invoices_placement', 'invoices', 'placements',
                          ['placement_id'], ['id'], source_schema=S, referent_schema=S)
    op.add_column('invoices', sa.Column('is_replacement', sa.Boolean(), nullable=False,
                                        server_default=sa.text('false')), schema=S)
    op.add_column('invoices', sa.Column('credit_note_of', UUID(as_uuid=True), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column('invoices', 'credit_note_of', schema=S)
    op.drop_column('invoices', 'is_replacement', schema=S)
    op.drop_constraint('fk_invoices_placement', 'invoices', schema=S, type_='foreignkey')
    op.drop_column('invoices', 'placement_id', schema=S)
    op.drop_column('clients', 'fee_percent', schema=S)
    op.drop_index('ix_placements_guarantee_until', table_name='placements', schema=S)
    op.drop_index('ix_placements_application_id', table_name='placements', schema=S)
    op.drop_table('placements', schema=S)
