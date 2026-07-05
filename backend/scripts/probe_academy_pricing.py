"""One-off A5 real-op verification on dev RDS — sps_app. Issue → take → grade →
assert on the enrollment row + the notification ledger:

  1. discount_percent stamped
  2. final_fee stamped AND == course.fee × (100−discount)/100 for the course's
     ACTUAL fee (read the course's real fee — do NOT assume 50000)
  3. status == offered
  4. the payment-link email present in the ledger (ConsoleChannel row, not sent)
     with the stub link shape

Flag flipped in-process (deployed service stays OFF). Self-cleans.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app.academy_pricing import compute_final_fee
from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import Notification
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Test

# a deliberately NON-default per-course fee so leg 2 proves it reads course.fee
PROBE_FEE = 47777


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
    test_id = None
    try:
        course = Course(tenant_id=tid, business_unit_id="ACADEMY", title="A5 Probe Course",
                        slug=f"a5probe-{uuid.uuid4().hex[:8]}", fee=PROBE_FEE)
        student = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="A5 Probe Student",
                          email=f"a5probe-{uuid.uuid4().hex[:6]}@local.test")
        db.add_all([course, student]); db.flush()
        cohort = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=course.id, name="Probe")
        db.add(cohort); db.flush()
        enr = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=cohort.id,
                         student_id=student.id, course_id=course.id, status="applied")
        db.add(enr); db.commit()
        made = [enr, cohort, student, course]

        # admin issue → take → grade 57/60 = 95.0 → 20%
        ctx = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY", user_id=None,
                             roles=("recruiter",))
        from app.routers.academy import issue_aptitude
        res = issue_aptitude(enrollment_id=enr.id, ctx=ctx, db=db, idempotency_key=None)
        token = res["take_path"].rsplit("/", 1)[-1]
        test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
        test_id = test.id
        frozen = test.served_questions
        answers = {f["qid"]: (f["correct"] if i < 57 else (f["correct"] + 1) % 4)
                   for i, f in enumerate(frozen)}
        from app.routers.take import submit_answers, SubmitIn
        submit_answers(token=token, body=SubmitIn(answers=answers), db=db)
        db.refresh(enr)

        # read the course's REAL fee back and assert final_fee derives from IT
        course_fee = db.execute(select(Course.fee).where(Course.id == course.id)).scalar_one()
        expected_fee = compute_final_fee(course_fee, int(enr.discount_percent))
        a1 = int(enr.discount_percent) == 20
        a2 = float(enr.final_fee) == expected_fee
        a3 = enr.status == "offered"
        note = db.execute(select(Notification).where(
            Notification.idempotency_key == f"academy:payment_link:{test.id}")).scalar_one_or_none()
        a4 = note is not None and "[STUB — A6/Part-D] /academy/pay/" in (note.rendered_body or "")

        print(f"1. discount_percent stamped: {enr.discount_percent} (==20) {'✅' if a1 else '❌'}")
        print(f"2. final_fee {enr.final_fee} == course.fee({course_fee}) × (100−20)/100 = "
              f"{expected_fee}  {'✅' if a2 else '❌'}  [proves it reads the real per-course fee, not 50000]")
        print(f"3. status == offered: {enr.status} {'✅' if a3 else '❌'}")
        print(f"4. payment-link email in ledger (stub link shape): {'✅' if a4 else '❌'}")
        ok = a1 and a2 and a3 and a4
    finally:
        db.rollback()
        if test_id is not None:
            db.execute(delete(Notification).where(
                Notification.idempotency_key == f"academy:payment_link:{test_id}"))
            db.execute(delete(Test).where(Test.id == test_id))
        for e in made:
            db.execute(delete(type(e)).where(type(e).id == e.id))
        db.commit(); db.close()
        print("5. probe rows cleaned")
    print("A5 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
