"""0006 candidate PII expand — encrypted + blind-index columns (Part 10)

Revision ID: 0006_candidate_pii_expand
Revises: 0005_dpdp_consent
Create Date: 2026-06-27

EXPAND phase of the PII-encryption rollout. Adds (nullable) encrypted columns
(phone_enc / pan_enc — bytea, AES-256-GCM envelope ciphertext) and deterministic
blind-index columns (phone_bidx / pan_bidx — bytea, HMAC-SHA256) to
staffing.candidates. The legacy plaintext phone/pan columns are LEFT IN PLACE here
and removed only in the later CONTRACT migration, after the app cut-over deploys.
Dedup unique constraints on the blind indexes are added in 0007 (after backfill).
Additive only; no data change.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_candidate_pii_expand'
down_revision = '0005_dpdp_consent'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.add_column('candidates', sa.Column('phone_enc', sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column('candidates', sa.Column('phone_bidx', sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column('candidates', sa.Column('pan_enc', sa.LargeBinary(), nullable=True), schema=SCHEMA)
    op.add_column('candidates', sa.Column('pan_bidx', sa.LargeBinary(), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column('candidates', 'pan_bidx', schema=SCHEMA)
    op.drop_column('candidates', 'pan_enc', schema=SCHEMA)
    op.drop_column('candidates', 'phone_bidx', schema=SCHEMA)
    op.drop_column('candidates', 'phone_enc', schema=SCHEMA)
