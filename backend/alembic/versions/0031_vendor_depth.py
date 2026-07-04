"""0031 vendor depth — contracts, client-dynamic rates, commission ledger (B.13)

Revision ID: 0031_vendor_depth
Revises: 0030_crm_leads
Create Date: 2026-07-04

Closes PENDING D3. Commission is CLIENT-DYNAMIC (settled): resolution =
per-placement override → vendor_client_rates (vendor×client) → vendor_contract
base (the contract valid AT placement.joined_on) → global default (config,
shipped None → 409 rather than an invented rate). Base = % of the PLACEMENT FEE
(SPS's earnings share), not CTC.

vendor_commissions is MATERIALIZED on purpose: the valid-at-placement-date rate
LOCK requires a persisted row (on-read would re-resolve with today's rates and
retro-alter history); it also carries the accrued→paid|void lifecycle.
UNIQUE(placement_id) = one commission per placement, structurally.
vendor_performance = read-model on-read (B.11 pattern), NO table.

Normal-DML; NOT in the append-only REVOKE list. Additive/reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0031_vendor_depth'
down_revision = '0030_crm_leads'
branch_labels = None
depends_on = None

S = 'staffing'
BU = "business_unit_id IN ('STAFFING','ACADEMY','CONSULTING')"


def _common():
    return [
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'vendor_contracts',
        *_common(),
        sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.vendors.id'),
                  nullable=False),
        sa.Column('base_commission_percent', sa.Numeric(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.CheckConstraint(BU, name='ck_vendor_contracts_business_unit'),
        sa.CheckConstraint("status IN ('active','expired','terminated')",
                           name='ck_vendor_contracts_status'),
        sa.CheckConstraint('valid_until IS NULL OR valid_until >= valid_from',
                           name='ck_vendor_contracts_window'),
        schema=S,
    )
    op.create_index('ix_vendor_contracts_vendor', 'vendor_contracts', ['vendor_id'], schema=S)

    op.create_table(
        'vendor_client_rates',
        *_common(),
        sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.vendors.id'),
                  nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.clients.id'),
                  nullable=False),
        sa.Column('commission_percent', sa.Numeric(), nullable=False),
        sa.CheckConstraint(BU, name='ck_vendor_client_rates_business_unit'),
        sa.UniqueConstraint('vendor_id', 'client_id', name='uq_vendor_client_rates'),
        schema=S,
    )

    op.create_table(
        'vendor_commissions',
        *_common(),
        sa.Column('vendor_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.vendors.id'),
                  nullable=False),
        sa.Column('placement_id', UUID(as_uuid=True), sa.ForeignKey(f'{S}.placements.id'),
                  nullable=False),
        sa.Column('resolved_percent', sa.Numeric(), nullable=False),
        sa.Column('base_amount', sa.Numeric(), nullable=False),      # the placement FEE
        sa.Column('commission_amount', sa.Numeric(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'accrued'")),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint(BU, name='ck_vendor_commissions_business_unit'),
        sa.CheckConstraint("status IN ('accrued','paid','void')",
                           name='ck_vendor_commissions_status'),
        sa.UniqueConstraint('placement_id', name='uq_vendor_commissions_placement'),
        schema=S,
    )
    op.create_index('ix_vendor_commissions_vendor', 'vendor_commissions',
                    ['vendor_id'], schema=S)


def downgrade() -> None:
    op.drop_index('ix_vendor_commissions_vendor', table_name='vendor_commissions', schema=S)
    op.drop_table('vendor_commissions', schema=S)
    op.drop_table('vendor_client_rates', schema=S)
    op.drop_index('ix_vendor_contracts_vendor', table_name='vendor_contracts', schema=S)
    op.drop_table('vendor_contracts', schema=S)
