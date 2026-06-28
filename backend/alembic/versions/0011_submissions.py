"""0011 submissions — submit candidate/application to client (Part 5)

Revision ID: 0011_submissions
Revises: 0010_erasure_state
Create Date: 2026-06-28

staffing.submissions: two-axis (tenant_id + business_unit_id TEXT+CHECK), FK to
applications, status CHECK (submitted/under_review/shortlisted/rejected),
client_feedback, submitted_by. New table only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_submissions'
down_revision = '0010_erasure_state'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.create_table(
        'submissions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Text(), server_default=sa.text("'submitted'"), nullable=False),
        sa.Column('client_feedback', sa.Text(), nullable=True),
        sa.Column('submitted_by', sa.UUID(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')", name='ck_submissions_business_unit'),
        sa.CheckConstraint("status IN ('submitted', 'under_review', 'shortlisted', 'rejected')", name='ck_submissions_status'),
        sa.ForeignKeyConstraint(['application_id'], [f'{SCHEMA}.applications.id'], name='fk_submissions_application'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_submissions_tenant_bu', 'submissions', ['tenant_id', 'business_unit_id'], schema=SCHEMA)
    op.create_index('ix_submissions_application_id', 'submissions', ['application_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_submissions_application_id', table_name='submissions', schema=SCHEMA)
    op.drop_index('ix_submissions_tenant_bu', table_name='submissions', schema=SCHEMA)
    op.drop_table('submissions', schema=SCHEMA)
