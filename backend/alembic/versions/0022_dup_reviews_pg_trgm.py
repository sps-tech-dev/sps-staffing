"""0022 duplicate detection — pg_trgm + candidate_dup_reviews + trigram index (B.3)

Revision ID: 0022_dup_reviews_pg_trgm
Revises: 0021_candidate_timeline
Create Date: 2026-07-04

- CREATE EXTENSION pg_trgm (public schema; mirrors the citext precedent in 0002;
  runs as master in the migrate task; pg_trgm is on the RDS allow-list).
- staffing.candidate_dup_reviews: the human review queue for FUZZY duplicate
  suspects (create-then-flag model — the incoming candidate is always created,
  then flagged). Normal business table: sps_app keeps full DML (NOT append-only,
  deliberately NOT in the bootstrap REVOKE list).
- GIN trigram index on candidates.full_name for the similarity scan.
  NOTE(prod): on a populated table this index should be built CONCURRENTLY
  outside a transaction; dev tables are ~empty so a plain build is instant.

Downgrade drops the index + table but NOT the extension (shared, like citext).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0022_dup_reviews_pg_trgm'
down_revision = '0021_candidate_timeline'
branch_labels = None
depends_on = None

S = 'staffing'


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")

    op.create_table(
        'candidate_dup_reviews',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        # the NEW/incoming candidate (create-then-flag: it already exists)
        sa.Column('candidate_id', UUID(as_uuid=True), nullable=False),
        # the suspected existing match (merge survivor if confirmed)
        sa.Column('matched_candidate_id', UUID(as_uuid=True), nullable=False),
        sa.Column('match_type', sa.Text(), nullable=False),
        sa.Column('score', sa.Numeric(), nullable=False),
        sa.Column('incoming_payload', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('reviewed_by', UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("match_type IN ('exact','fuzzy')", name='ck_dup_reviews_match_type'),
        sa.CheckConstraint("status IN ('pending','merged','dismissed')", name='ck_dup_reviews_status'),
        schema=S,
    )
    op.create_index('ix_dup_reviews_tenant_status', 'candidate_dup_reviews',
                    ['tenant_id', 'status'], schema=S)

    op.create_index('ix_candidates_full_name_trgm', 'candidates', ['full_name'],
                    unique=False, schema=S, postgresql_using='gin',
                    postgresql_ops={'full_name': 'gin_trgm_ops'})


def downgrade() -> None:
    op.drop_index('ix_candidates_full_name_trgm', table_name='candidates', schema=S)
    op.drop_index('ix_dup_reviews_tenant_status', table_name='candidate_dup_reviews', schema=S)
    op.drop_table('candidate_dup_reviews', schema=S)
    # pg_trgm intentionally NOT dropped (shared extension, citext precedent)
