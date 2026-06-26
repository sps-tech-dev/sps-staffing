"""create four platform schemas (shared, staffing, academy, consulting)

Revision ID: 0001_create_schemas
Revises:
Create Date: 2026-06-26

First migration. Creates ONLY the four empty schemas in sps_platform_dev — no
tables/models. Schema-per-vertical with a shared spine (see DECISIONS: one shared
DB, schema-per-vertical). `shared` also holds the alembic_version table.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_create_schemas"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ["shared", "staffing", "academy", "consulting"]


def upgrade() -> None:
    # Idempotent: env.py already ensures `shared` exists for alembic_version;
    # this re-asserts all four so the DB topology is fully declared here.
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def downgrade() -> None:
    # CAUTION: dropping a schema removes everything in it. Safe now (schemas are
    # empty); becomes destructive once tables exist. RESTRICT refuses to drop a
    # non-empty schema, so a careless downgrade can't silently delete data.
    # Note: dropping `shared` also removes the alembic_version table.
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" RESTRICT')
