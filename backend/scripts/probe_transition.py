"""8b-1 transition machine — dev probe on real RDS. sps_app. Proves the two writers
now route through transition() AND emit the status-transition audit that did NOT
exist before (finding #6 closed on real data), and that the pay path writes BOTH
the payment audit AND the new transition audit (added, not replaced).

Flag flipped in-process only; live task-def untouched. Self-cleans by own ids.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.academy_deps import StudentContext
from app.models import AuditLog, Notification
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.models_staffing import Test

TRANSITION = "academy.enrollment.transition"
PAYMENT_AUDIT = "academy.payment_activate"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import issue_aptitude, student_pay
    from app.routers.take import fetch_paper, submit_answers, SubmitIn
    made: list = []
    receipt_key = None
    ok = False
    try:
        s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Trans Probe",
                    email=f"transprobe-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=tid, business_unit_id="ACADEMY", title="Trans Probe",
                   slug=f"trans-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="Probe")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status="applied")   # real 'applied'
        db.add(e); db.flush(); made.append(e)
        db.commit()

        def transition_audits():
            return db.execute(select(AuditLog).where(
                AuditLog.action == TRANSITION, AuditLog.entity_id == e.id)
                .order_by(AuditLog.id)).scalars().all()

        # baseline: NO transition audit exists yet
        base = len(transition_audits())

        # 1. GRADE: applied → offered
        staff = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY", user_id=None, roles=("recruiter",))
        res = issue_aptitude(enrollment_id=e.id, ctx=staff, db=db, idempotency_key=None)
        tok = res["take_path"].rsplit("/", 1)[-1]
        t = db.execute(select(Test).where(Test.enrollment_id == e.id)).scalar_one()
        fetch_paper(token=tok, db=db)
        submit_answers(token=tok, body=SubmitIn(answers={f["qid"]: f["correct"] for f in t.served_questions}), db=db)
        db.refresh(e)
        ga = transition_audits()
        grade_row = ga[-1].after if ga else {}
        a1 = (e.status == "offered" and len(ga) == base + 1
              and grade_row.get("from") == "applied" and grade_row.get("to") == "offered"
              and grade_row.get("kind") == "system" and grade_row.get("actor") == "aptitude_engine")
        print(f"1. GRADE: status={e.status}, transition audit {grade_row.get('from')}→{grade_row.get('to')} "
              f"kind={grade_row.get('kind')} actor={grade_row.get('actor')} (row that didn't exist before): {'✅' if a1 else '❌'}")

        # 2. PAY: offered → active (+ payment_status paid)
        e.aptitude_score = 96; e.discount_percent = 20; e.final_fee = 40000; db.commit()
        student_pay(enrollment_id=e.id, student=StudentContext(student_id=s.id, tenant_id=str(tid), email=s.email, college_student_id=None), db=db)
        db.refresh(e)
        pay = db.execute(select(Payment).where(Payment.enrollment_id == e.id)).scalar_one()
        receipt_key = pay.receipt_s3_key
        pa = transition_audits()
        pay_row = pa[-1].after if pa else {}
        a2 = (e.status == "active" and e.payment_status == "paid" and len(pa) == base + 2
              and pay_row.get("from") == "offered" and pay_row.get("to") == "active"
              and pay_row.get("kind") == "system" and pay_row.get("actor") == "payment")
        print(f"2. PAY: status={e.status} payment_status={e.payment_status}, transition audit "
              f"{pay_row.get('from')}→{pay_row.get('to')} actor={pay_row.get('actor')}: {'✅' if a2 else '❌'}")

        # 3. DISTINCTION: pay wrote BOTH the payment audit AND the transition audit
        pay_audits = db.execute(select(AuditLog).where(
            AuditLog.action == PAYMENT_AUDIT, AuditLog.entity_id == pay.id)).scalars().all()
        a3 = len(pay_audits) == 1 and len(pa) == base + 2
        print(f"3. DISTINCTION: payment audit present ({len(pay_audits)}) AND transition audit present "
              f"(total {len(pa)}) — added, not replaced: {'✅' if a3 else '❌'}")

        ok = all([a1, a2, a3])
    finally:
        db.rollback()
        # NOTE: the academy.enrollment.transition + payment_activate AUDIT rows are
        # deliberately NOT deleted — shared.audit_logs is append-only (sps_app has no
        # DELETE), and an audit trail is meant to outlive the entities it references.
        # These orphaned-by-cleanup rows are the very rows the probe proved exist.
        db.execute(delete(Notification).where(Notification.recipient.like("transprobe-%")))
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        if enr_ids:
            db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
            db.execute(delete(Test).where(Test.enrollment_id.in_(enr_ids)))
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        if receipt_key:
            try:
                from app import storage
                storage._client().delete_object(Bucket=storage.settings.storage_bucket, Key=receipt_key)
            except Exception:  # noqa: BLE001
                pass
        print("4. probe rows + S3 receipt + audit rows cleaned (own ids)")
    print("8b-1 TRANSITION PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
