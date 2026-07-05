"""Small FE#5 dev confirm — /me/enrollments now returns course.fee for the
authenticated student, AND cross-student isolation still holds (the field addition
didn't touch session-scoping). Flag flipped in-process only. Self-cleans."""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app.config import settings
from app.db import get_sessionmaker
from app.academy_deps import StudentContext
from app.models_academy import Cohort, Course, Enrollment, Student


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import my_enrollments
    made: list = []
    ok = False
    try:
        def mk(tag, fee, status, score, disc, final):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"F5 {tag}",
                        email=f"f5probe-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title=f"F5 {tag}",
                       slug=f"f5-{uuid.uuid4().hex[:8]}", fee=fee)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="B")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status=status,
                           aptitude_score=score, discount_percent=disc, final_fee=final)
            db.add(e); db.flush(); made.append(e)
            return s, e
        a, ea = mk("A", 55000, "offered", 88, 15, 46750)
        b, eb = mk("B", 70000, "offered", 99, 20, 56000)
        db.commit()
        ctxA = StudentContext(student_id=a.id, tenant_id=str(tid), email=a.email, college_student_id=None)

        rows = my_enrollments(student=ctxA, db=db)
        row = rows[0]
        r_fee = row["course"]["fee"] == 55000.0 and row["final_fee"] == 46750.0
        import json
        blob = json.dumps(rows)
        r_iso = str(eb.id) not in blob and "70000" not in blob and "56000" not in blob   # B's list/final absent
        print(f"1. /me/enrollments returns course.fee (list): {row['course']['fee']} + final {row['final_fee']} "
              f"{'✅' if r_fee else '❌'}")
        print(f"2. isolation still holds (A cannot see B's list/final/id): {'✅' if r_iso else '❌'}")
        ok = r_fee and r_iso
    finally:
        db.rollback()
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("3. probe rows cleaned")
    print("FE#5 DEV CONFIRM: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
