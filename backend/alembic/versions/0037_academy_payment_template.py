"""0037 seed the academy payment-link notification template (A5)

Revision ID: 0037_academy_payment_template
Revises: 0036_academy_aptitude_bank
Create Date: 2026-07-05

DATA-ONLY (no schema change — A5's pricing columns enrollments.discount_percent /
final_fee already exist from A1). Adds the `academy_payment_link` notification
template so B.10 can render the post-grade payment-link email. Reuses the same
idempotent app.academy_seed.seed_notification_templates (the other two academy
templates already exist → skipped). [FOUNDER DRAFT] copy. Reversible.
"""
from alembic import op

from app.academy_seed import seed_notification_templates

revision = '0037_academy_payment_template'
down_revision = '0036_academy_aptitude_bank'
branch_labels = None
depends_on = None


def upgrade() -> None:
    seed_notification_templates(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM shared.notification_templates WHERE code = 'academy_payment_link'")
