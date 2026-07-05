"""0036 seed the course-independent academy aptitude bank (A4 part 2)

Revision ID: 0036_academy_aptitude_bank
Revises: 0035_tests_vertical_agnostic
Create Date: 2026-07-05

DATA-ONLY seed (no schema change) — the course-INDEPENDENT entrance aptitude
bank (quant/logical/verbal/english) the academy 60Q test draws from. Reuses the
A1 seed convention exactly: an idempotent app.academy_seed.seed_aptitude_bank
shared between this migration and the test fixture (E2E-3 reproducibility). The
bank + 60 questions are business_unit_id='ACADEMY' in staffing.question_banks/
questions (the BU column keeps them isolated from staffing papers — the issue
seam filters by BU). [SAMPLE] content is a dev placeholder. Reversible.
"""
from alembic import op
import sqlalchemy as sa

from app.academy_seed import seed_aptitude_bank

revision = '0036_academy_aptitude_bank'
down_revision = '0035_tests_vertical_agnostic'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tenant_id = conn.execute(sa.text(
        "SELECT id FROM shared.tenants WHERE code = 'SPS001'")).scalar_one_or_none()
    if tenant_id is not None:
        seed_aptitude_bank(conn, tenant_id)


def downgrade() -> None:
    op.execute(
        "DELETE FROM staffing.questions q USING staffing.question_banks b "
        "WHERE q.bank_id = b.id AND b.business_unit_id = 'ACADEMY' "
        "AND b.name = 'Academy Entrance Aptitude'")
    op.execute(
        "DELETE FROM staffing.question_banks WHERE business_unit_id = 'ACADEMY' "
        "AND name = 'Academy Entrance Aptitude'")
