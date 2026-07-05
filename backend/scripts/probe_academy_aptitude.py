"""One-off A4-P2 real-op verification on dev RDS — sps_app. TWO mandatory legs:

  A. STAFFING issue still draws a FULL 30Q paper on dev — proves the new BU filter
     did NOT silently drop dev's pre-existing staffing question rows (i.e. they
     really are tagged business_unit_id='STAFFING'). <30 or empty → the probe
     FAILS loudly (BU-tagging on dev needs a backfill before A4-P2 is safe).
  B. ACADEMY flow on dev: admin issue → take (/take/{token}) → auto-grade →
     enrollment.aptitude_score stamped + status applied→tested.

Flag flipped in-process (deployed service stays OFF). Self-cleans.
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid

from sqlalchemy import delete, func, select, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Application, Candidate, Job, Test
from app.routers.assessments import select_bank_paper

TAG = "[A4 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    settings.feature_academy = True
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    made = []
    try:
        # ── LEG A: staffing still draws a full 30Q paper on dev ──
        n_staff_active = db.execute(text(
            "SELECT count(*) FROM staffing.questions q JOIN staffing.question_banks b "
            "ON b.id=q.bank_id WHERE q.tenant_id=:t AND q.is_active AND b.is_active "
            "AND b.business_unit_id='STAFFING'"), {"t": str(tid)}).scalar_one()
        frozen_staff = select_bank_paper(db, tid, "STAFFING", settings.test_question_count)
        if len(frozen_staff) < settings.test_question_count:
            print(f"❌ LEG A FAIL: STAFFING drew {len(frozen_staff)} < {settings.test_question_count} "
                  f"(active STAFFING questions on dev: {n_staff_active}). "
                  f"The BU filter dropped rows — dev staffing questions need a business_unit_id "
                  f"backfill BEFORE A4-P2 is safe. STOP.")
            return 1
        print(f"1. LEG A: STAFFING issue draws a FULL {len(frozen_staff)}Q paper on dev "
              f"({n_staff_active} active STAFFING questions present) ✅")

        # ── LEG B: academy issue → take → grade → enrollment stamp ──
        course = Course(tenant_id=tid, business_unit_id="ACADEMY", title=f"Probe Course {TAG}",
                        slug=f"probe-{uuid.uuid4().hex[:8]}")
        student = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"Probe Student {TAG}",
                          email=f"a4probe-{uuid.uuid4().hex[:6]}@local.test")
        db.add_all([course, student]); db.flush()
        cohort = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=course.id, name="Probe Batch")
        db.add(cohort); db.flush()
        enr = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=cohort.id,
                         student_id=student.id, course_id=course.id, status="applied")
        db.add(enr); db.commit()
        made = [enr, cohort, student, course]

        ctx = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY", user_id=None,
                             roles=("recruiter",))
        from app.routers.academy import issue_aptitude
        res = issue_aptitude(enrollment_id=enr.id, ctx=ctx, db=db, idempotency_key=None)
        assert res["question_count"] == 60 and res["time_limit_minutes"] == 60
        token = res["take_path"].rsplit("/", 1)[-1]
        test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
        assert (test.business_unit_id == "ACADEMY" and test.student_id == student.id
                and test.application_id is None and test.candidate_id is None)
        print("2. LEG B: admin issue → ACADEMY pairing, 60Q/60min on dev RDS ✅")

        from app.routers.take import submit_answers, SubmitIn
        frozen = test.served_questions
        answers = {f["qid"]: f["correct"] for f in frozen}
        submit_answers(token=token, body=SubmitIn(answers=answers), db=db)
        db.refresh(enr)
        assert enr.aptitude_score == 100.0 and enr.status == "tested"
        print(f"3. LEG B: take → auto-grade → enrollment stamped "
              f"(aptitude_score={enr.aptitude_score}, status={enr.status}) ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Test).where(Test.tenant_id == tid, Test.business_unit_id == "ACADEMY",
                   Test.enrollment_id.in_(select(Enrollment.id).where(
                       Enrollment.tenant_id == tid, Enrollment.business_unit_id == "ACADEMY"))))
        for e in made:
            db.execute(delete(type(e)).where(type(e).id == e.id))
        db.commit(); db.close()
        print("4. probe rows cleaned")
    print("A4-P2 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
