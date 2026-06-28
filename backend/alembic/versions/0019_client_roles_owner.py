"""0019 client roles + job owner — client-internal roles + owner_user_id (nested)

Revision ID: 0019_client_roles_owner
Revises: 0018_client_reg_requests
Create Date: 2026-06-28

Adds `role` (client_admin/client_manager) to shared.client_users, and a denormalized
`owner_user_id` (the owning client portal user) to staffing.jobs + applications/
submissions/offers/interviews so the BASE repo can owner-scope a client_manager's view
by a column filter (no cross-manager visibility). owner_user_id is a SOFT ref to
shared.users (no cross-schema FK). Backfilled from the job. Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0019_client_roles_owner'
down_revision = '0018_client_reg_requests'
branch_labels = None
depends_on = None

S = 'staffing'
_OWNED = ('jobs', 'applications', 'submissions', 'offers', 'interviews')


def upgrade() -> None:
    # client-internal role
    op.add_column('client_users',
                  sa.Column('role', sa.Text(), server_default=sa.text("'client_admin'"), nullable=False),
                  schema='shared')
    op.create_check_constraint('ck_client_users_role', 'client_users',
                               "role IN ('client_admin','client_manager')", schema='shared')

    # owner_user_id on jobs + dependent pipeline tables
    for t in _OWNED:
        op.add_column(t, sa.Column('owner_user_id', sa.UUID(), nullable=True), schema=S)
        op.create_index(f'ix_{t}_owner_user_id', t, ['owner_user_id'], schema=S)

    # backfill: jobs have no prior client owner; dependents inherit from the job
    for t in ('applications', 'submissions', 'offers', 'interviews'):
        if t == 'applications':
            op.execute(f"UPDATE {S}.applications a SET owner_user_id = j.owner_user_id "
                       f"FROM {S}.jobs j WHERE j.id = a.job_id")
        else:
            op.execute(f"UPDATE {S}.{t} x SET owner_user_id = a.owner_user_id "
                       f"FROM {S}.applications a WHERE a.id = x.application_id")


def downgrade() -> None:
    for t in reversed(_OWNED):
        op.drop_index(f'ix_{t}_owner_user_id', table_name=t, schema=S)
        op.drop_column(t, 'owner_user_id', schema=S)
    op.drop_constraint('ck_client_users_role', 'client_users', schema='shared', type_='check')
    op.drop_column('client_users', 'role', schema='shared')
