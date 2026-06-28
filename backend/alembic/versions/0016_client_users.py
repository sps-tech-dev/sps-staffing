"""0016 client_users — client-portal identity binding (nested isolation)

Revision ID: 0016_client_users
Revises: 0015_vendors
Create Date: 2026-06-28

shared.client_users: binds a `users` login to a specific staffing.clients company
(tenant_id + client_id) with an approval lifecycle. A client portal user's session
is scoped to BOTH tenant_id (existing) AND client_id (new dimension). client_id is a
SOFT reference to staffing.clients (no cross-schema FK — shared must not depend on a
vertical). New table only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_client_users'
down_revision = '0015_vendors'
branch_labels = None
depends_on = None

SCHEMA = 'shared'


def upgrade() -> None:
    op.create_table(
        'client_users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=True),   # soft ref to staffing.clients (bound on approval)
        sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('pending','active','rejected','suspended')", name='ck_client_users_status'),
        sa.ForeignKeyConstraint(['tenant_id'], [f'{SCHEMA}.tenants.id'], name='fk_client_users_tenant'),
        sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name='fk_client_users_user'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_client_users_tenant_user'),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA,
    )
    op.create_index('ix_client_users_user', 'client_users', ['user_id'], schema=SCHEMA)
    op.create_index('ix_client_users_client', 'client_users', ['client_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index('ix_client_users_client', table_name='client_users', schema=SCHEMA)
    op.drop_index('ix_client_users_user', table_name='client_users', schema=SCHEMA)
    op.drop_table('client_users', schema=SCHEMA)
