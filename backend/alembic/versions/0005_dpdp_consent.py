"""0005 dpdp + consent — consents ledger + dpdp_requests (Part 10 / F6)

Revision ID: 0005_dpdp_consent
Revises: 0004_staffing_core
Create Date: 2026-06-27

Two shared-schema tables for DPDP data-principal rights:
- consents: APPEND-ONLY consent event ledger (grant/withdraw per purpose); current
  state = latest row per (subject_user_id, purpose). CHECK on purpose.
- dpdp_requests: export / erasure requests with a status lifecycle (CHECKs on
  kind + status). Both tenant-scoped and FK'd to shared.tenants / shared.users.
No new extension (gen_random_uuid + schema exist since 0002).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0005_dpdp_consent'
down_revision = '0004_staffing_core'
branch_labels = None
depends_on = None

SCHEMA = 'shared'


def upgrade() -> None:
    op.create_table(
        'consents',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('subject_user_id', sa.UUID(), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('policy_version', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("purpose IN ('data_processing','marketing','cookies')", name='ck_consents_purpose'),
        sa.ForeignKeyConstraint(['tenant_id'], [f'{SCHEMA}.tenants.id'], name='fk_consents_tenant'),
        sa.ForeignKeyConstraint(['subject_user_id'], [f'{SCHEMA}.users.id'], name='fk_consents_subject'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_consents_subject_purpose', 'consents',
                    ['subject_user_id', 'purpose', 'created_at'], unique=False, schema=SCHEMA)

    op.create_table(
        'dpdp_requests',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('subject_user_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('export','erasure')", name='ck_dpdp_requests_kind'),
        sa.CheckConstraint("status IN ('pending','processing','completed','rejected')", name='ck_dpdp_requests_status'),
        sa.ForeignKeyConstraint(['tenant_id'], [f'{SCHEMA}.tenants.id'], name='fk_dpdp_requests_tenant'),
        sa.ForeignKeyConstraint(['subject_user_id'], [f'{SCHEMA}.users.id'], name='fk_dpdp_requests_subject'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_dpdp_requests_subject', 'dpdp_requests',
                    ['subject_user_id', 'created_at'], unique=False, schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_dpdp_requests_subject', table_name='dpdp_requests', schema=SCHEMA)
    op.drop_table('dpdp_requests', schema=SCHEMA)
    op.drop_index('ix_consents_subject_purpose', table_name='consents', schema=SCHEMA)
    op.drop_table('consents', schema=SCHEMA)
