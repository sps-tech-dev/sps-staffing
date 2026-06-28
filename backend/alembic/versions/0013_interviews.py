"""0013 interviews — schedule + track interviews against applications (Part 5)

Revision ID: 0013_interviews
Revises: 0012_offers
Create Date: 2026-06-28

staffing.interviews: two-axis, FK→applications, scheduled_at, mode CHECK
(phone/video/onsite), status CHECK (scheduled/completed/cancelled/no_show),
interviewer_name, feedback. New table only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_interviews'
down_revision = '0012_offers'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.create_table(
        'interviews',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mode', sa.Text(), server_default=sa.text("'video'"), nullable=False),
        sa.Column('status', sa.Text(), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column('interviewer_name', sa.Text(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_interviews_business_unit'),
        sa.CheckConstraint("status IN ('scheduled', 'completed', 'cancelled', 'no_show')", name='ck_interviews_status'),
        sa.CheckConstraint("mode IN ('phone', 'video', 'onsite')", name='ck_interviews_mode'),
        sa.ForeignKeyConstraint(['application_id'], [f'{SCHEMA}.applications.id'], name='fk_interviews_application'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_interviews_tenant_bu', 'interviews', ['tenant_id', 'business_unit_id'], schema=SCHEMA)
    op.create_index('ix_interviews_application_id', 'interviews', ['application_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_interviews_application_id', table_name='interviews', schema=SCHEMA)
    op.drop_index('ix_interviews_tenant_bu', table_name='interviews', schema=SCHEMA)
    op.drop_table('interviews', schema=SCHEMA)
