"""0014 invoices — placement invoice structure + 15% fee (Part 5)

Revision ID: 0014_invoices
Revises: 0013_interviews
Create Date: 2026-06-28

staffing.invoices: two-axis, FK→applications (placement) + clients. base_amount,
fee_percent (default 15 = SPS placement fee, a BUSINESS term), fee_amount; GST/TDS
percent+amount columns are NULLable and NOT defaulted — tax rates await legal
confirmation (PENDING Q1) and are never hardcoded. total_amount, currency, status
CHECK (draft/issued/paid/cancelled). New table only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_invoices'
down_revision = '0013_interviews'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.create_table(
        'invoices',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),
        sa.Column('base_amount', sa.Numeric(), nullable=True),
        sa.Column('fee_percent', sa.Numeric(), server_default=sa.text('15'), nullable=False),
        sa.Column('fee_amount', sa.Numeric(), nullable=True),
        sa.Column('gst_percent', sa.Numeric(), nullable=True),
        sa.Column('gst_amount', sa.Numeric(), nullable=True),
        sa.Column('tds_percent', sa.Numeric(), nullable=True),
        sa.Column('tds_amount', sa.Numeric(), nullable=True),
        sa.Column('total_amount', sa.Numeric(), nullable=True),
        sa.Column('currency', sa.Text(), server_default=sa.text("'INR'"), nullable=False),
        sa.Column('status', sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_invoices_business_unit'),
        sa.CheckConstraint("status IN ('draft', 'issued', 'paid', 'cancelled')", name='ck_invoices_status'),
        sa.ForeignKeyConstraint(['application_id'], [f'{SCHEMA}.applications.id'], name='fk_invoices_application'),
        sa.ForeignKeyConstraint(['client_id'], [f'{SCHEMA}.clients.id'], name='fk_invoices_client'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_invoices_tenant_bu', 'invoices', ['tenant_id', 'business_unit_id'], schema=SCHEMA)
    op.create_index('ix_invoices_client_id', 'invoices', ['client_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_invoices_client_id', table_name='invoices', schema=SCHEMA)
    op.drop_index('ix_invoices_tenant_bu', table_name='invoices', schema=SCHEMA)
    op.drop_table('invoices', schema=SCHEMA)
