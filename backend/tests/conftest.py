"""Shared test fixtures.

E2E-3: the aptitude assessment tests (test_assessments.py) need an active question
bank with EXACTLY 12 active questions for the SPS001 tenant (they assert
`question_count == min(test_question_count, 12)`). Migration 0026 data-seeds a
SAMPLE bank, so a freshly-migrated clone has it — but that seed is ordinary DML a
sweep can delete permanently, with nothing to recreate it (which is exactly how
the suite broke mid-E2E-1). This session-scoped fixture makes the tests
independent of whatever is (or isn't) in the DB: it deactivates any pre-existing
active questions, installs a deterministic 12-question neutral bank for the run,
and restores the prior state afterwards. Test-only — it does NOT touch the
migration seed path or the assessment engine.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select, update

from app.db import get_sessionmaker
from app.models import Tenant
from app.models_staffing import Question, QuestionBank

# 12 neutral SAMPLE questions. Constraints the tests rely on: exactly 12, valid
# correct_index (0-3), and NO substring "correct" anywhere (the no-answer-leak
# check asserts `"correct" not in response.text`).
_SEED_QUESTIONS = [
    ("[FIXTURE] 12 + 15 = ?", ["25", "27", "29", "31"], 1),
    ("[FIXTURE] Which is a prime number?", ["21", "27", "29", "33"], 2),
    ("[FIXTURE] Next in series 2, 4, 8, 16, …?", ["24", "30", "32", "34"], 2),
    ("[FIXTURE] 15% of 200 = ?", ["25", "30", "35", "40"], 1),
    ("[FIXTURE] The opposite of 'expand' is?", ["grow", "widen", "contract", "extend"], 2),
    ("[FIXTURE] If a=3 and b=4, a squared plus b squared = ?", ["21", "24", "25", "49"], 2),
    ("[FIXTURE] A car travels 60 km in 1 hour; distance in 3 hours?", ["120", "150", "180", "200"], 2),
    ("[FIXTURE] Which word is a synonym of 'rapid'?", ["slow", "swift", "heavy", "late"], 1),
    ("[FIXTURE] 100 divided by 4 = ?", ["20", "24", "25", "30"], 2),
    ("[FIXTURE] Complete: Monday, Tuesday, Wednesday, …?", ["Friday", "Sunday", "Thursday", "Saturday"], 2),
    ("[FIXTURE] Which is heaviest: 1kg feathers, 1kg iron, 1kg water?", ["feathers", "iron", "water", "all equal"], 3),
    ("[FIXTURE] 7 x 8 = ?", ["54", "56", "58", "64"], 1),
]


@pytest.fixture(scope="session", autouse=True)
def aptitude_seed_bank():
    """Guarantee exactly the 12-question active bank the assessment tests expect,
    independent of migration-seed / dev-DB state. Restores prior state on teardown."""
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()

    # deactivate any pre-existing active questions so the served count is exactly 12
    prior_active = db.execute(select(Question.id).where(
        Question.tenant_id == sps.id, Question.is_active.is_(True))).scalars().all()
    if prior_active:
        db.execute(update(Question).where(Question.id.in_(prior_active)).values(is_active=False))

    bank = QuestionBank(tenant_id=sps.id, business_unit_id="STAFFING",
                        name="TEST FIXTURE — General Aptitude", category="aptitude",
                        is_active=True)
    db.add(bank)
    db.flush()
    for stem, options, correct in _SEED_QUESTIONS:
        db.add(Question(tenant_id=sps.id, business_unit_id="STAFFING", bank_id=bank.id,
                        category="aptitude", difficulty="medium", stem=stem,
                        options=options, correct_index=correct, is_active=True))
    db.commit()

    yield

    # teardown: remove the fixture bank + its questions, reactivate the prior set
    db.execute(delete(Question).where(Question.bank_id == bank.id))
    db.execute(delete(QuestionBank).where(QuestionBank.id == bank.id))
    if prior_active:
        db.execute(update(Question).where(Question.id.in_(prior_active)).values(is_active=True))
    db.commit()
    db.close()


# A1: the 8 academy courses are migration-seeded, but (E2E-3 lesson) tests must
# not depend on uncodified/persistent DB state. This session-scoped fixture
# ensures the 8 courses exist for SPS001 from the SAME source of truth the
# migration uses (idempotent create-if-absent), so academy tests pass from any
# DB state (fresh, seeded, or swept). Test-only.
@pytest.fixture(scope="session", autouse=True)
def academy_course_seed():
    from app.academy_seed import seed_courses
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    seed_courses(db.connection(), sps.id)
    db.commit()
    db.close()
    yield


# A3: the two academy notification templates are migration-seeded, but (E2E-3
# lesson) tests must not depend on uncodified DB state. Idempotent ensure from
# the same source of truth the migration uses.
@pytest.fixture(scope="session", autouse=True)
def academy_notification_templates():
    from app.academy_seed import seed_notification_templates
    db = get_sessionmaker()()
    seed_notification_templates(db.connection())
    db.commit()
    db.close()
    yield
