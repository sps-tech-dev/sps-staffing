"""0012 offers — offer creation (CTC, joining date, RTR / acceptance) (Part 5)

Revision ID: 0012_offers
Revises: 0011_submissions
Create Date: 2026-06-28

staffing.offers: two-axis, FK→applications, ctc (Numeric), joining_date (Date),
status CHECK (draft/released/accepted/declined/withdrawn), rtr_signed_at,
accepted_at. New table only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_offers'
down_revision = '0011_submissions'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.create_table(
        'offers',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('ctc', sa.Numeric(), nullable=True),
        sa.Column('joining_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('rtr_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_offers_business_unit'),
        sa.CheckConstraint("status IN ('draft', 'released', 'accepted', 'declined', 'withdrawn')", name='ck_offers_status'),
        sa.ForeignKeyConstraint(['application_id'], [f'{SCHEMA}.applications.id'], name='fk_offers_application'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_offers_tenant_bu', 'offers', ['tenant_id', 'business_unit_id'], schema=SCHEMA)
    op.create_index('ix_offers_application_id', 'offers', ['application_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_offers_application_id', table_name='offers', schema=SCHEMA)
    op.drop_index('ix_offers_tenant_bu', table_name='offers', schema=SCHEMA)
    op.drop_table('offers', schema=SCHEMA)
