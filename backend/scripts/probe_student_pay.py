"""FE#6 student-initiate pay — dev probe on real RDS (money-adjacent). sps_app.

1. Student pays their OWN offered enrolment → paid + active + paid_at, amount ==
   the enrolment's final_fee (read off the row), receipt PDF actually fetched from
   real S3 (pre-signed GET → %PDF bytes), confirmation email in the ledger.
2. ISOLATION: A pays B's enrolment id → 404 AND nothing fired on B (B still
   offered/unpaid, 0 payment rows) — the action-on-wrong-row guard.
3. Redelivery no-op: student re-hits own paid enrolment → same shape, no 2nd
   activation/receipt/email.
4. Wrong-state: student pays a not-offered (tested) enrolment → 409, nothing
   activated.

Flag flipped `settings.feature_academy = True` IN THIS PROBE PROCESS ONLY (one-off
ECS task); the live service task-def is untouched → stays OFF. Self-cleans all
rows + the S3 receipt object.
"""
from __future__ import annotations

import sys
import urllib.request
import uuid

from sqlalchemy import delete, func, select, text

from app.config import settings
from app.db import get_sessionmaker
from app import storage
from app.academy_deps import StudentContext
from app.models import Notification
from app.models_academy import Cohort, Course, Enrollment, Payment, Student


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only; service stays off
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import student_pay
    made: list = []
    receipt_key = None
    ok = False
    try:
        def mk(tag, status="offered", final=40000.0):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"Pay6 {tag}",
                        email=f"pay6probe-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title=f"Pay6 {tag}",
                       slug=f"pay6-{uuid.uuid4().hex[:8]}", fee=50000)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="B")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status=status,
                           aptitude_score=96, discount_percent=20, final_fee=final)
            db.add(e); db.flush(); made.append(e)
            return s, e

        a, ea = mk("A", final=40000.0)
        b, eb = mk("B", final=48000.0)
        t_s, t_e = mk("T", status="tested")
        db.commit()
        ctxA = StudentContext(student_id=a.id, tenant_id=str(tid), email=a.email, college_student_id=None)
        ctxT = StudentContext(student_id=t_s.id, tenant_id=str(tid), email=t_s.email, college_student_id=None)

        # 1. A pays their OWN offered enrolment
        final_fee = float(db.execute(select(Enrollment.final_fee).where(Enrollment.id == ea.id)).scalar_one())
        res = student_pay(enrollment_id=ea.id, student=ctxA, db=db)
        pay = db.execute(select(Payment).where(Payment.enrollment_id == ea.id)).scalar_one()
        enr = db.get(Enrollment, ea.id)
        receipt_key = pay.receipt_s3_key
        s3_ok = False
        if res.get("receipt_url"):
            with urllib.request.urlopen(res["receipt_url"], timeout=20) as r:
                data = r.read()
            s3_ok = r.status == 200 and data[:4] == b"%PDF" and len(data) > 500
        n_email = db.execute(select(func.count()).select_from(Notification).where(
            Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one()
        a1 = (res["status"] == "paid" and res["enrollment_status"] == "active"
              and pay.paid_at is not None and enr.status == "active"
              and float(pay.amount) == final_fee)
        print(f"1. own pay: status={res['status']} enr={res['enrollment_status']} paid_at set "
              f"amount={pay.amount}==final_fee({final_fee}) {'✅' if a1 else '❌'}")
        print(f"   receipt fetched from S3 (%PDF bytes): {'✅' if s3_ok else '❌'} | email in ledger: n={n_email} "
              f"{'✅' if n_email == 1 else '❌'}")

        # 2. ISOLATION: A pays B's enrolment id → 404, nothing fired on B
        from fastapi import HTTPException
        iso_404 = False
        try:
            student_pay(enrollment_id=eb.id, student=ctxA, db=db)
        except HTTPException as ex:
            iso_404 = ex.status_code == 404
            db.rollback()
        db.expire_all()
        eb2 = db.get(Enrollment, eb.id)
        b_untouched = (eb2.status == "offered" and eb2.payment_status == "pending"
                       and db.execute(select(func.count()).select_from(Payment).where(
                           Payment.enrollment_id == eb.id)).scalar_one() == 0)
        print(f"2. ISOLATION: A→B's enrolment = 404 ({iso_404}); B untouched "
              f"(offered/pending, 0 payments): {'✅' if (iso_404 and b_untouched) else '❌'}")

        # 3. Redelivery no-op: A re-hits their own paid enrolment
        paid_at_1 = pay.paid_at
        student_pay(enrollment_id=ea.id, student=ctxA, db=db)
        db.expire_all()
        n_pay = db.execute(select(func.count()).select_from(Payment).where(
            Payment.enrollment_id == ea.id)).scalar_one()
        pay2 = db.execute(select(Payment).where(Payment.enrollment_id == ea.id)).scalar_one()
        n_email2 = db.execute(select(func.count()).select_from(Notification).where(
            Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one()
        a3 = n_pay == 1 and pay2.paid_at == paid_at_1 and n_email2 == 1
        print(f"3. redelivery no-op: 1 payment row, same paid_at, 1 email: {'✅' if a3 else '❌'}")

        # 4. Wrong-state: pay a not-offered (tested) enrolment → 409
        got_409 = False
        try:
            student_pay(enrollment_id=t_e.id, student=ctxT, db=db)
        except HTTPException as ex:
            got_409 = ex.status_code == 409 and ex.detail.get("code") == "STATUS_INVALID"
            db.rollback()
        db.expire_all()
        a4 = got_409 and db.execute(select(func.count()).select_from(Payment).where(
            Payment.enrollment_id == t_e.id)).scalar_one() == 0
        print(f"4. wrong-state (tested) → 409, nothing activated: {'✅' if a4 else '❌'}")

        ok = all([a1, s3_ok, n_email == 1, iso_404, b_untouched, a3, a4])
    finally:
        db.rollback()
        db.execute(delete(Notification).where(Notification.recipient.like("pay6probe-%")))
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        if enr_ids:
            db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        if receipt_key:
            try:
                storage._client().delete_object(Bucket=storage.settings.storage_bucket, Key=receipt_key)
                print("5. probe rows + S3 receipt object cleaned")
            except Exception as ex:  # noqa: BLE001
                print(f"5. rows cleaned; S3 receipt delete warning: {ex}")
        else:
            print("5. probe rows cleaned")
    print("FE#6 STUDENT-PAY PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
