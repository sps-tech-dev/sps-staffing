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
