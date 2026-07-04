"""0030 CRM — shared leads + activities (B.12)

Revision ID: 0030_crm_leads
Revises: 0029_notifications
Create Date: 2026-07-04

SHARED schema on purpose (settled decision A): staffing BD uses these now;
Consulting (B.18) reuses the SAME tables/endpoints via business_unit_id scoping —
reuse is scoping, not a fork.

Lead contact fields are BUSINESS contacts (a company's BD card), not candidate
PII — plaintext like client/vendor contact fields (stated at STOP-1).

Normal-DML tables, NOT in the append-only REVOKE list. Additive/reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, UUID

revision = '0030_crm_leads'
down_revision = '0029_notifications'
branch_labels = None
depends_on = None

BU_CHECK = "business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')"
STAGES = "stage IN ('new','qualified','proposal','negotiation','won','lost')"


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('company', sa.Text(), nullable=False),
        sa.Column('contact_name', sa.Text(), nullable=True),
        sa.Column('contact_email', CITEXT(), nullable=True),
        sa.Column('contact_phone', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=True),
        sa.Column('stage', sa.Text(), nullable=False, server_default=sa.text("'new'")),
        sa.Column('lost_reason', sa.Text(), nullable=True),
        sa.Column('converted_client_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU_CHECK, name='ck_leads_business_unit'),
        sa.CheckConstraint(STAGES, name='ck_leads_stage'),
        schema='shared',
    )
    op.create_index('ix_leads_tenant_stage', 'leads', ['tenant_id', 'stage'], schema='shared')

    op.create_table(
        'activities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('lead_id', UUID(as_uuid=True),
                  sa.ForeignKey('shared.leads.id'), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actor_id', UUID(as_uuid=True), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint(BU_CHECK, name='ck_activities_business_unit'),
        schema='shared',
    )
    op.create_index('ix_activities_lead_occurred', 'activities',
                    ['lead_id', 'occurred_at'], schema='shared')


def downgrade() -> None:
    op.drop_index('ix_activities_lead_occurred', table_name='activities', schema='shared')
    op.drop_table('activities', schema='shared')
    op.drop_index('ix_leads_tenant_stage', table_name='leads', schema='shared')
    op.drop_table('leads', schema='shared')
