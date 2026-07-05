"""0038 academy.payments — add paid_at + receipt_s3_key (A6 activation)

Revision ID: 0038_academy_payment_cols
Revises: 0037_academy_payment_template
Create Date: 2026-07-05

A6 payment activation needs two columns the A1 payments table (0033) does not have:
  - paid_at (timestamptz, NULL): stamped when a payment is confirmed paid (the stub
    confirm today, the HMAC-verified Razorpay webhook in Part-D — SAME activation seam).
  - receipt_s3_key (text, NULL): the S3 key of the generated receipt PDF, so the row
    (and A9's student dashboard) can re-fetch the receipt via a pre-signed URL.

Additive, nullable, reversible. No backfill (existing payment rows are pre-A6 and
carry NULL for both — semantically correct: not-yet-paid / no receipt). The amount,
status ('created'/'paid'/...) and provider/provider_ref columns already exist and
are reused unchanged (provider_ref will hold the Razorpay payment id in Part-D).
"""
from alembic import op
import sqlalchemy as sa

revision = '0038_academy_payment_cols'
down_revision = '0037_academy_payment_template'
branch_labels = None
depends_on = None

S = 'academy'


def upgrade() -> None:
    op.add_column('payments', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True), schema=S)
    op.add_column('payments', sa.Column('receipt_s3_key', sa.Text(), nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column('payments', 'receipt_s3_key', schema=S)
    op.drop_column('payments', 'paid_at', schema=S)
