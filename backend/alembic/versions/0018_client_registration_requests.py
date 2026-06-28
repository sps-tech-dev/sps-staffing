"""0018 client registration requests — public client self-registration (Task 2)

Revision ID: 0018_client_registration_requests
Revises: 0017_pipeline_client_id
Create Date: 2026-06-28

shared.client_registration_requests: inbound PENDING client signup (grants nothing
until admin approval). Contact phone is encrypted (bytea ciphertext + blind index);
email is CITEXT. status CHECK pending/approved/rejected. New table only.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0018_client_reg_requests'
down_revision = '0017_pipeline_client_id'
branch_labels = None
depends_on = None

SCHEMA = 'shared'


def upgrade() -> None:
    op.create_table(
        'client_registration_requests',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('company_name', sa.Text(), nullable=False),
        sa.Column('industry', sa.Text(), nullable=True),
        sa.Column('contact_person', sa.Text(), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('phone_enc', sa.LargeBinary(), nullable=True),
        sa.Column('phone_bidx', sa.LargeBinary(), nullable=True),
        sa.Column('website', sa.Text(), nullable=True),
        sa.Column('company_size', sa.Text(), nullable=True),
        sa.Column('consent_data_processing', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('policy_version', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name='ck_client_reg_status'),
        sa.ForeignKeyConstraint(['tenant_id'], [f'{SCHEMA}.tenants.id'], name='fk_client_reg_tenant'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_client_reg_tenant_status', 'client_registration_requests',
                    ['tenant_id', 'status'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_client_reg_tenant_status', table_name='client_registration_requests', schema=SCHEMA)
    op.drop_table('client_registration_requests', schema=SCHEMA)
