"""0026 aptitude test engine — banks, questions, tests + SAMPLE seed (B.7)

Revision ID: 0026_aptitude_tests
Revises: 0025_internal_evaluations
Create Date: 2026-07-04

Three normal business tables (sps_app full DML — deliberately NOT in the
append-only REVOKE list):
  - question_banks / questions: correct_index lives ONLY server-side; the
    take-test surface never receives it.
  - tests: one aptitude attempt; link_token_hash = SHA-256 of the one-time
    candidate token (raw token never stored); served_questions = the FROZEN
    paper (ids + shuffled options + frozen correct answers) — grading never
    re-queries the bank.

Seed: one clearly-marked SAMPLE bank + 12 placeholder questions for the owner
tenant SPS001 (real question CONTENT is a Part-C input from the user). The seed
lives in this migration (0003 owner-seed precedent); downgrade drops the tables
and the seed with them. Additive/reversible.
"""
import uuid as _uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0026_aptitude_tests'
down_revision = '0025_internal_evaluations'
branch_labels = None
depends_on = None

S = 'staffing'
BU_CHECK = "business_unit_id IN ('STAFFING', 'ACADEMY', 'CONSULTING')"

SAMPLE_QUESTIONS = [
    # (difficulty, stem, options, correct_index) — SAMPLE placeholders, not real content
    ("easy", "[SAMPLE] 12 + 15 = ?", ["25", "27", "29", "31"], 1),
    ("easy", "[SAMPLE] Which is a prime number?", ["21", "27", "29", "33"], 2),
    ("easy", "[SAMPLE] Next in series 2, 4, 8, 16, …?", ["24", "30", "32", "34"], 2),
    ("easy", "[SAMPLE] 15% of 200 = ?", ["25", "30", "35", "40"], 1),
    ("medium", "[SAMPLE] A train covers 120 km in 2h. Speed?", ["50 km/h", "55 km/h", "60 km/h", "65 km/h"], 2),
    ("medium", "[SAMPLE] If 3x - 7 = 14, x = ?", ["5", "6", "7", "8"], 2),
    ("medium", "[SAMPLE] Average of 10, 20, 30, 40 = ?", ["20", "25", "30", "35"], 1),
    ("medium", "[SAMPLE] CODE is to DPEF as MIND is to?", ["NJOE", "NKOF", "OJPE", "NJPE"], 0),
    ("hard", "[SAMPLE] Two pipes fill a tank in 6h and 8h; together?", ["3.43h", "3.5h", "3.6h", "4h"], 0),
    ("hard", "[SAMPLE] Compound interest on 1000 @10% for 2y?", ["200", "210", "220", "231"], 1),
    ("hard", "[SAMPLE] Probability of two heads in two coin tosses?", ["1/2", "1/3", "1/4", "3/4"], 2),
    ("hard", "[SAMPLE] Work: A alone 12d, A+B 8d. B alone?", ["20d", "22d", "24d", "26d"], 2),
]


def upgrade() -> None:
    op.create_table(
        'question_banks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU_CHECK, name='ck_question_banks_business_unit'),
        schema=S,
    )
    op.create_index('ix_question_banks_tenant_bu', 'question_banks',
                    ['tenant_id', 'business_unit_id'], schema=S)

    op.create_table(
        'questions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('bank_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.question_banks.id'), nullable=False),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('difficulty', sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('stem', sa.Text(), nullable=False),
        sa.Column('options', JSONB(), nullable=False),
        sa.Column('correct_index', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU_CHECK, name='ck_questions_business_unit'),
        sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name='ck_questions_difficulty'),
        schema=S,
    )
    op.create_index('ix_questions_bank_id', 'questions', ['bank_id'], schema=S)

    op.create_table(
        'tests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('application_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.applications.id'), nullable=False),
        sa.Column('candidate_id', UUID(as_uuid=True),
                  sa.ForeignKey(f'{S}.candidates.id'), nullable=False),
        sa.Column('link_token_hash', sa.Text(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'issued'")),
        sa.Column('attempt_no', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('served_questions', JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('score', sa.Numeric(), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('proctor_flags', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(BU_CHECK, name='ck_tests_business_unit'),
        sa.CheckConstraint("status IN ('issued','started','submitted','expired')",
                           name='ck_tests_status'),
        sa.UniqueConstraint('link_token_hash', name='uq_tests_link_token_hash'),
        schema=S,
    )
    op.create_index('ix_tests_application_id', 'tests', ['application_id'], schema=S)

    # ── SAMPLE seed for the owner tenant (real content = Part-C input) ──
    conn = op.get_bind()
    tenant_id = conn.execute(sa.text(
        "SELECT id FROM shared.tenants WHERE code = 'SPS001'")).scalar_one_or_none()
    if tenant_id is not None:
        bank_id = str(_uuid.uuid4())
        conn.execute(sa.text(
            f"INSERT INTO {S}.question_banks (id, tenant_id, business_unit_id, name, category) "
            "VALUES (:i, :t, 'STAFFING', "
            "'SAMPLE — General Aptitude (placeholder content, replace via Part C)', 'aptitude')"),
            {"i": bank_id, "t": str(tenant_id)})
        for diff, stem, options, correct in SAMPLE_QUESTIONS:
            conn.execute(sa.text(
                f"INSERT INTO {S}.questions (tenant_id, business_unit_id, bank_id, category, "
                "difficulty, stem, options, correct_index) VALUES "
                "(:t, 'STAFFING', :b, 'aptitude', :d, :s, CAST(:o AS jsonb), :c)"),
                {"t": str(tenant_id), "b": bank_id, "d": diff, "s": stem,
                 "o": __import__("json").dumps(options), "c": correct})


def downgrade() -> None:
    op.drop_index('ix_tests_application_id', table_name='tests', schema=S)
    op.drop_table('tests', schema=S)
    op.drop_index('ix_questions_bank_id', table_name='questions', schema=S)
    op.drop_table('questions', schema=S)
    op.drop_index('ix_question_banks_tenant_bu', table_name='question_banks', schema=S)
    op.drop_table('question_banks', schema=S)
