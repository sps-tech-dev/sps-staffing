"""0040 seed the academy aptitude-invite notification template (FE#4b)

Revision ID: 0040_academy_invite_tmpl
Revises: 0039_academy_active_template
Create Date: 2026-07-05

DATA-ONLY (no schema change). Adds `academy_aptitude_invite` (carries the
/take/{token} link to the student) via the idempotent seed_notification_templates.
Same pattern as 0037/0039. [FOUNDER DRAFT] copy. Reversible.
"""
from alembic import op

from app.academy_seed import seed_notification_templates

revision = '0040_academy_invite_tmpl'
down_revision = '0039_academy_active_template'
branch_labels = None
depends_on = None


def upgrade() -> None:
    seed_notification_templates(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM shared.notification_templates WHERE code = 'academy_aptitude_invite'")
