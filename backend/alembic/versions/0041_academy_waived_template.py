"""0041 seed the academy fee-waived notification template (8b-3)

Revision ID: 0041_academy_waived_template
Revises: 0040_academy_invite_tmpl
Create Date: 2026-07-08

DATA-ONLY (no schema change — 'waived' is an existing enrolment.payment_status
CHECK value). Adds the `academy_enrolment_waived` template (fee waived → enrolment
active; must NOT say "payment received") via the idempotent
app.academy_seed.seed_notification_templates (existing templates skipped). Same
pattern as 0037/0039/0040. [FOUNDER DRAFT] copy. Reversible.
"""
from alembic import op

from app.academy_seed import seed_notification_templates

revision = '0041_academy_waived_template'
down_revision = '0040_academy_invite_tmpl'
branch_labels = None
depends_on = None


def upgrade() -> None:
    seed_notification_templates(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM shared.notification_templates WHERE code = 'academy_enrolment_waived'")
