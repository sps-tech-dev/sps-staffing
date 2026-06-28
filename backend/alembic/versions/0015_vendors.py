"""0015 vendors — vendor + vendor_submission core (Part 5)

Revision ID: 0015_vendors
Revises: 0014_invoices
Create Date: 2026-06-28

Vendor / sub-vendor CORE: staffing.vendors + staffing.vendor_submissions (two-axis).
vendor_contracts / vendor_commissions / vendor_performance are a tracked follow-up
(PENDING). New tables only.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0015_vendors'
down_revision = '0014_invoices'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.create_table(
        'vendors',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('contact_email', postgresql.CITEXT(), nullable=True),
        sa.Column('contact_phone', sa.Text(), nullable=True),
        sa.Column('commission_percent', sa.Numeric(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_vendors_business_unit'),
        sa.CheckConstraint("status IN ('active', 'inactive')", name='ck_vendors_status'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_vendors_tenant_bu', 'vendors', ['tenant_id', 'business_unit_id'], schema=SCHEMA)

    op.create_table(
        'vendor_submissions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'submitted'"), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_vendor_submissions_business_unit'),
        sa.CheckConstraint("status IN ('submitted', 'shortlisted', 'rejected', 'placed')", name='ck_vendor_submissions_status'),
        sa.ForeignKeyConstraint(['vendor_id'], [f'{SCHEMA}.vendors.id'], name='fk_vendor_submissions_vendor'),
        sa.ForeignKeyConstraint(['candidate_id'], [f'{SCHEMA}.candidates.id'], name='fk_vendor_submissions_candidate'),
        sa.ForeignKeyConstraint(['job_id'], [f'{SCHEMA}.jobs.id'], name='fk_vendor_submissions_job'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_vendor_submissions_tenant_bu', 'vendor_submissions', ['tenant_id', 'business_unit_id'], schema=SCHEMA)
    op.create_index('ix_vendor_submissions_vendor_id', 'vendor_submissions', ['vendor_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_vendor_submissions_vendor_id', table_name='vendor_submissions', schema=SCHEMA)
    op.drop_index('ix_vendor_submissions_tenant_bu', table_name='vendor_submissions', schema=SCHEMA)
    op.drop_table('vendor_submissions', schema=SCHEMA)
    op.drop_index('ix_vendors_tenant_bu', table_name='vendors', schema=SCHEMA)
    op.drop_table('vendors', schema=SCHEMA)
