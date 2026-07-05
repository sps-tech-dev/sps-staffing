"""0039 seed the academy enrolment-active notification template (A6)

Revision ID: 0039_academy_active_template
Revises: 0038_academy_payment_cols
Create Date: 2026-07-05

DATA-ONLY (no schema change — A6's payment columns land in 0038). Adds the
`academy_enrolment_active` template (payment confirmed → enrolment active) via the
idempotent app.academy_seed.seed_notification_templates (existing templates
skipped). Same pattern as 0037. [FOUNDER DRAFT] copy. Reversible.
"""
from alembic import op

from app.academy_seed import seed_notification_templates

revision = '0039_academy_active_template'
down_revision = '0038_academy_payment_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    seed_notification_templates(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM shared.notification_templates WHERE code = 'academy_enrolment_active'")
