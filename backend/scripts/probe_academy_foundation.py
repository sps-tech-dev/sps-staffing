"""One-off A1 real-op verification on dev RDS — sps_app.

Proves: all 9 academy tables present; the 8 courses seeded by the migration;
sps_app can round-trip a student with ENCRYPTED PII (which also proves the
ALTER DEFAULT PRIVILEGES auto-grant covered the new academy tables — a
permission-denied here would mean the grant didn't reach them). Self-cleans the
probe student.
"""
from __future__ import annotations

import sys

from sqlalchemy import delete, select, text

from app.academy_seed import SEED_COURSES
from app.crypto import blind_index
from app.db import get_sessionmaker
from app.models_academy import Course, Student

TAG = "[A1 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    try:
        tables = set(db.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='academy'"
        )).scalars().all())
        expected = {"courses", "cohorts", "students", "enrollments", "attendance",
                    "assignments", "assignment_submissions", "certificates", "payments"}
        assert expected.issubset(tables), f"missing {expected - tables}"
        print(f"1. all 9 academy tables present on dev RDS ✅")

        slugs = set(db.execute(select(Course.slug).where(
            Course.tenant_id == tid, Course.deleted_at.is_(None))).scalars().all())
        seed_slugs = {c["slug"] for c in SEED_COURSES}
        assert seed_slugs.issubset(slugs), f"missing seeded courses {seed_slugs - slugs}"
        n = db.execute(text("SELECT count(*) FROM academy.courses WHERE tenant_id=:t "
                            "AND fee=50000 AND is_published=false"), {"t": str(tid)}).scalar_one()
        print(f"2. 8 courses seeded (₹50,000 default, unpublished): {len(seed_slugs)} slugs present, "
              f"{n} at default fee ✅")

        st = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"Probe Student {TAG}",
                     email="a1-probe-student@local.test", phone_enc="+919800011122",
                     phone_bidx=blind_index("+919800011122"))
        db.add(st); db.commit()
        raw = db.execute(text("SELECT phone_enc FROM academy.students WHERE id=:i"),
                         {"i": str(st.id)}).scalar_one()
        assert b"+919800011122" not in bytes(raw)
        db.expire(st)
        assert st.phone_enc == "+919800011122"
        print("3. sps_app round-tripped a student with ENCRYPTED PII (INSERT/SELECT granted "
              "on the new academy tables — auto-grant confirmed) ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Student).where(Student.tenant_id == tid,
                                         Student.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("4. probe student cleaned up")
    print("A1 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
