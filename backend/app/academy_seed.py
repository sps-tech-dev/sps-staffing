"""Canonical Academy seed data — the single source of truth for the 8 scaffolded
courses (plan v2 §2.11). Imported by BOTH migration 0033 (production/dev seed) and
the test fixture (tests/conftest.py) so there is no drift and no uncodified seed
state (the E2E-3 lesson). `seed_courses` is idempotent — safe to call repeatedly.

Content is deliberately placeholder ('[YOUR CONTENT — placeholder]'): A2 adds
staff CRUD + publish; these ship is_published=false. Fees default to ₹50,000
(decision 6); durations/levels are placeholders the founder fills in.
"""
from __future__ import annotations

import sqlalchemy as sa

DEFAULT_FEE = 50000
PLACEHOLDER = "[YOUR CONTENT — placeholder]"

# (slug, title) — the 8 courses. slug is stable + URL-safe; title is display.
SEED_COURSES: list[dict] = [
    {"slug": "dotnet-full-stack", "title": ".NET Full-Stack Development"},
    {"slug": "ai-ml", "title": "AI / Machine Learning"},
    {"slug": "python", "title": "Python Programming"},
    {"slug": "data-analyst", "title": "Data Analyst"},
    {"slug": "data-engineer", "title": "Data Engineer"},
    {"slug": "cloud", "title": "Cloud (AWS / Azure / GCP)"},
    {"slug": "java-full-stack", "title": "Java Full-Stack Development"},
    {"slug": "angular-react", "title": "Angular / React"},
]


def seed_courses(conn: sa.engine.Connection, tenant_id) -> int:
    """Idempotent: insert any of the 8 courses not already present for this tenant
    (keyed on the per-tenant UNIQUE slug). Returns the number inserted. Uses raw
    SQL so it works identically from an Alembic migration and from a live session
    connection."""
    inserted = 0
    for c in SEED_COURSES:
        exists = conn.execute(sa.text(
            "SELECT 1 FROM academy.courses WHERE tenant_id = :t AND slug = :s "
            "AND deleted_at IS NULL"),
            {"t": str(tenant_id), "s": c["slug"]}).scalar_one_or_none()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO academy.courses "
            "(tenant_id, business_unit_id, title, slug, description, syllabus, "
            " level, duration_weeks, fee, currency, is_published, status) VALUES "
            "(:t, 'ACADEMY', :title, :slug, :desc, :syl, :lvl, :dur, :fee, 'INR', false, 'draft')"),
            {"t": str(tenant_id), "title": c["title"], "slug": c["slug"],
             "desc": PLACEHOLDER, "syl": PLACEHOLDER, "lvl": PLACEHOLDER, "dur": None,
             "fee": DEFAULT_FEE})
        inserted += 1
    return inserted


# ── A3: notification templates (global, no tenant) — single source of truth for
# the migration seed AND the test fixture (E2E-3 reproducibility). channel_type
# 'email' is the INTENDED channel; NOTIFY_CHANNEL_OVERRIDE routes to console in
# dev. Subject/body are [FOUNDER DRAFT] placeholders (STOP-3 — not final copy).
SEED_NOTIFICATION_TEMPLATES: list[dict] = [
    {"code": "student_welcome", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] Welcome to SPS Academy, {full_name}",
     "body": "[FOUNDER DRAFT] Hi {full_name}, your application for {course} is received. "
             "Our team will share your entrance aptitude link shortly."},
    {"code": "admin_new_student_application", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] New academy application: {full_name}",
     "body": "[FOUNDER DRAFT] {full_name} ({email}) applied for {course}. "
             "College: {college}. Review + trigger the aptitude link from the admin dashboard."},
    # A5 — payment-link email (STUB link; real Razorpay link = A6/Part-D).
    {"code": "academy_payment_link", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] Your SPS Academy enrolment — {course}",
     "body": "[FOUNDER DRAFT] Hi {full_name}, based on your entrance aptitude you earned a "
             "{discount_percent}% discount on {course}. Your enrolment fee is {final_fee} {currency} "
             "(pre-tax). Complete payment here: {payment_link}"},
    # A6 — payment confirmed → enrolment ACTIVE.
    {"code": "academy_enrolment_active", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] Enrolment confirmed — {course}",
     "body": "[FOUNDER DRAFT] Hi {full_name}, we received your payment of {amount} {currency} for "
             "{course}. Your enrolment is now ACTIVE. Your receipt is attached to your student "
             "dashboard. Welcome to SPS Academy!"},
    # 8b-3 — fee WAIVED → enrolment ACTIVE (no payment; must NOT say "payment received").
    {"code": "academy_enrolment_waived", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] Enrolment confirmed — {course}",
     "body": "[FOUNDER DRAFT] Hi {full_name}, the fee for {course} has been WAIVED and your "
             "enrolment is now ACTIVE. No payment is due. Welcome to SPS Academy!"},
    # A4/FE#4b — aptitude-invite carrying the one-time /take/{token} link to the student.
    {"code": "academy_aptitude_invite", "channel_type": "email",
     "subject": "[FOUNDER DRAFT] Your SPS Academy entrance test — {course}",
     "body": "[FOUNDER DRAFT] Hi {full_name}, your entrance aptitude test for {course} is ready. "
             "Take it here: {take_link} (valid until {valid_until})."},
]


def seed_notification_templates(conn: sa.engine.Connection) -> int:
    """Idempotent insert of the academy notification templates (keyed on the
    global-unique code). Returns the number inserted."""
    inserted = 0
    for t in SEED_NOTIFICATION_TEMPLATES:
        exists = conn.execute(sa.text(
            "SELECT 1 FROM shared.notification_templates WHERE code = :c"),
            {"c": t["code"]}).scalar_one_or_none()
        if exists:
            continue
        conn.execute(sa.text(
            "INSERT INTO shared.notification_templates (code, channel_type, subject, body) "
            "VALUES (:c, :ch, :s, :b)"),
            {"c": t["code"], "ch": t["channel_type"], "s": t["subject"], "b": t["body"]})
        inserted += 1
    return inserted


# ── A4: course-INDEPENDENT aptitude bank (decision 1) — the single source of
# truth for the migration seed AND the test fixture (E2E-3 reproducibility).
# Categories = quant / logical / verbal / english; selection is by aptitude
# category, NOT by course. MINIMUM to draw a 60Q paper = 60 active questions.
# CARRY-FORWARD (BUILD-LOG): a PRODUCTION bank must be a pool MUCH larger than 60
# for question-level paper variety / anti-leak — with exactly 60, papers differ
# only by option-shuffle. [SAMPLE] content is a dev placeholder; real = [YOUR CONTENT].
APTITUDE_BANK_NAME = "Academy Entrance Aptitude"
_APT_CATEGORIES = ("quant", "logical", "verbal", "english")


def _sample_aptitude_questions() -> list[dict]:
    # 60 neutral [SAMPLE] questions (15 per category). Stems/options carry NO
    # substring "correct" (the no-answer-leak check asserts it never appears).
    out = []
    for cat in _APT_CATEGORIES:
        for i in range(15):
            out.append({
                "category": cat, "difficulty": "medium",
                "stem": f"[SAMPLE] {cat} item {i + 1}: choose the best option.",
                "options": [f"option A{i}", f"option B{i}", f"option C{i}", f"option D{i}"],
                "correct_index": i % 4,
            })
    return out


def seed_aptitude_bank(conn: sa.engine.Connection, tenant_id) -> int:
    """Idempotent: create the academy aptitude bank + its 60 questions for this
    tenant if absent (keyed on the bank name + business_unit). Returns questions
    inserted (0 if already present)."""
    bank_id = conn.execute(sa.text(
        "SELECT id FROM staffing.question_banks WHERE tenant_id = :t "
        "AND business_unit_id = 'ACADEMY' AND name = :n AND deleted_at IS NULL"),
        {"t": str(tenant_id), "n": APTITUDE_BANK_NAME}).scalar_one_or_none()
    if bank_id is not None:
        return 0
    bank_id = conn.execute(sa.text(
        "INSERT INTO staffing.question_banks (tenant_id, business_unit_id, name, category, is_active) "
        "VALUES (:t, 'ACADEMY', :n, 'aptitude', true) RETURNING id"),
        {"t": str(tenant_id), "n": APTITUDE_BANK_NAME}).scalar_one()
    n = 0
    for q in _sample_aptitude_questions():
        conn.execute(sa.text(
            "INSERT INTO staffing.questions (tenant_id, business_unit_id, bank_id, category, "
            "difficulty, stem, options, correct_index, is_active) VALUES "
            "(:t, 'ACADEMY', :b, :cat, :d, :s, CAST(:o AS jsonb), :c, true)"),
            {"t": str(tenant_id), "b": str(bank_id), "cat": q["category"], "d": q["difficulty"],
             "s": q["stem"], "o": __import__("json").dumps(q["options"]), "c": q["correct_index"]})
        n += 1
    return n
