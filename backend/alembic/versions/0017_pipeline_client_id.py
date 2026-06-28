"""0017 pipeline client_id — denormalize owning client onto applications + workflow

Revision ID: 0017_pipeline_client_id
Revises: 0016_client_users
Create Date: 2026-06-28

Adds a denormalized client_id (FK staffing.clients, nullable) to applications,
submissions, offers, interviews so the BASE repository can client-scope the entire
pipeline by a column filter (nested client isolation, can't be forgotten). Backfills
from the job's client_id. jobs + invoices already carry client_id; candidates stay
tenant-scoped (the talent pool is NOT client-owned — clients see candidates only via
their own client-scoped submissions/applications). Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = '0017_pipeline_client_id'
down_revision = '0016_client_users'
branch_labels = None
depends_on = None

S = 'staffing'
_TABLES = ('applications', 'submissions', 'offers', 'interviews')


def upgrade() -> None:
    for t in _TABLES:
        op.add_column(t, sa.Column('client_id', sa.UUID(), nullable=True), schema=S)
        op.create_foreign_key(f'fk_{t}_client', t, 'clients', ['client_id'], ['id'],
                              source_schema=S, referent_schema=S)
        op.create_index(f'ix_{t}_client_id', t, ['client_id'], schema=S)

    # backfill: applications from job; the rest from their application
    op.execute(f"UPDATE {S}.applications a SET client_id = j.client_id "
               f"FROM {S}.jobs j WHERE j.id = a.job_id")
    for t in ('submissions', 'offers', 'interviews'):
        op.execute(f"UPDATE {S}.{t} x SET client_id = a.client_id "
                   f"FROM {S}.applications a WHERE a.id = x.application_id")


def downgrade() -> None:
    for t in _TABLES:
        op.drop_index(f'ix_{t}_client_id', table_name=t, schema=S)
        op.drop_constraint(f'fk_{t}_client', t, schema=S, type_='foreignkey')
        op.drop_column(t, 'client_id', schema=S)
