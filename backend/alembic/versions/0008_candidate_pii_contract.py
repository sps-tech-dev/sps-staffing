"""0008 candidate PII contract — drop legacy plaintext phone/pan (Part 10)

Revision ID: 0008_candidate_pii_contract
Revises: 0007_candidate_pii_backfill
Create Date: 2026-06-27

CONTRACT phase: the app now reads/writes only the encrypted columns (phone_enc /
pan_enc) + blind indexes, so the legacy plaintext columns are removed. Run as a
SEPARATE deploy AFTER the expand+backfill+cutover deploy is live, so no running
code still references these columns.

NOTE (prod): on an environment with live candidate traffic, precede this with a
deploy that stops MAPPING the plaintext columns (so in-flight tasks don't SELECT
them during the migrate→deploy rollover). On dev there is no candidate traffic
(login is deferred), so the rollover window is a non-issue.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_candidate_pii_contract'
down_revision = '0007_candidate_pii_backfill'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    op.drop_column('candidates', 'phone', schema=SCHEMA)
    op.drop_column('candidates', 'pan', schema=SCHEMA)


def downgrade() -> None:
    # Re-add the (empty) plaintext columns; data is NOT restored — it lives only
    # in the encrypted columns now.
    op.add_column('candidates', sa.Column('pan', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('candidates', sa.Column('phone', sa.Text(), nullable=True), schema=SCHEMA)
