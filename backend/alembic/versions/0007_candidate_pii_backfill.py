"""0007 candidate PII backfill + dedup uniques (Part 10 / Part 19)

Revision ID: 0007_candidate_pii_backfill
Revises: 0006_candidate_pii_expand
Create Date: 2026-06-27

Backfills the encrypted + blind-index columns from any existing plaintext
phone/pan (dev: test data only), then adds the dedup UNIQUE constraints on the
blind indexes. The backfill encrypts with the SAME key mode the app uses (KMS in
the deployed migrate task; LOCAL key for the local loop), so the app can decrypt
what this writes. Uniques are added AFTER backfill so pre-existing data can't
fail constraint creation mid-derive.

NOTE: requires the PII keys to be available to the migrate task (PII_KMS_KEY_ID +
PII_INDEX_KEY in KMS mode; the migrate task role needs kms:GenerateDataKey).
"""
from alembic import op
import sqlalchemy as sa

from app.crypto import blind_index, encrypt

revision = '0007_candidate_pii_backfill'
down_revision = '0006_candidate_pii_expand'
branch_labels = None
depends_on = None

SCHEMA = 'staffing'


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        f"SELECT id, phone, pan FROM {SCHEMA}.candidates "
        "WHERE phone IS NOT NULL OR pan IS NOT NULL"
    )).fetchall()
    upd = sa.text(
        f"UPDATE {SCHEMA}.candidates "
        "SET phone_enc=:pe, phone_bidx=:pb, pan_enc=:ae, pan_bidx=:ab WHERE id=:id"
    )
    for rid, phone, pan in rows:
        conn.execute(upd, {
            "pe": encrypt(phone), "pb": blind_index(phone),
            "ae": encrypt(pan), "ab": blind_index(pan), "id": rid,
        })

    op.create_unique_constraint('uq_candidates_tenant_phone_bidx', 'candidates',
                                ['tenant_id', 'phone_bidx'], schema=SCHEMA)
    op.create_unique_constraint('uq_candidates_tenant_pan_bidx', 'candidates',
                                ['tenant_id', 'pan_bidx'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_constraint('uq_candidates_tenant_pan_bidx', 'candidates', schema=SCHEMA, type_='unique')
    op.drop_constraint('uq_candidates_tenant_phone_bidx', 'candidates', schema=SCHEMA, type_='unique')
    # The backfilled ciphertext/blind-index values are left in place (reversing
    # would require re-deriving plaintext); the expand migration's downgrade drops
    # the columns entirely if a full rollback is needed.
