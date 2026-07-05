"""One-off A6 real-op verification on dev RDS — sps_app. Full chain
issue→take→grade→pay, then the two properties that make the stub trustworthy as a
webhook model: (i) double-confirm no-op, (ii) wrong-state 409. Reads the
enrollment's ACTUAL final_fee and asserts amount against it (no assumed number),
and actually fetches the receipt PDF from S3 via a pre-signed GET. Self-cleans
(rows + the S3 receipt object).
"""
from __future__ import annotations

import sys
import uuid

import urllib.request

from sqlalchemy import delete, func, select, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app import storage
from app.models import Notification
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.models_staffing import Test

PROBE_FEE = 44444   # non-default → final_fee derives from the real per-course value


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    settings.feature_academy = True
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY", user_id=None,
                         roles=("recruiter",))
    ok = False
    made = []
    receipt_key = None
    try:
        course = Course(tenant_id=tid, business_unit_id="ACADEMY", title="A6 Probe Course",
                        slug=f"a6probe-{uuid.uuid4().hex[:8]}", fee=PROBE_FEE)
        student = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="A6 Probe Student",
                          email=f"a6probe-{uuid.uuid4().hex[:6]}@local.test")
        db.add_all([course, student]); db.flush()
        cohort = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=course.id, name="Probe")
        db.add(cohort); db.flush()
        enr = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=cohort.id,
                         student_id=student.id, course_id=course.id, status="applied")
        db.add(enr); db.commit()
        made = [enr, cohort, student, course]

        # issue → take → grade 57/60 → A5 stamps final_fee + status=offered
        from app.routers.academy import issue_aptitude, confirm_payment
        res = issue_aptitude(enrollment_id=enr.id, ctx=ctx, db=db, idempotency_key=None)
        token = res["take_path"].rsplit("/", 1)[-1]
        test = db.execute(select(Test).where(Test.enrollment_id == enr.id)).scalar_one()
        from app.routers.take import submit_answers, SubmitIn
        frozen = test.served_questions
        submit_answers(token=token, body=SubmitIn(
            answers={f["qid"]: (f["correct"] if i < 57 else (f["correct"] + 1) % 4)
                     for i, f in enumerate(frozen)}), db=db)
        db.refresh(enr)
        final_fee = float(enr.final_fee)
        assert enr.status == "offered", enr.status

        # ── happy path: pay ──
        confirm_payment(enrollment_id=enr.id, ctx=ctx, db=db)
        db.expire_all()
        pay = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
        enr = db.get(Enrollment, enr.id)
        receipt_key = pay.receipt_s3_key
        a_amount = float(pay.amount) == final_fee
        a_paid = pay.status == "paid" and pay.paid_at is not None
        a_enr = (enr.status == "active" and enr.payment_status == "paid"
                 and enr.payment_id == pay.id)
        # actually FETCH the receipt PDF from S3 via pre-signed GET
        s3_ok = False
        if receipt_key:
            url = storage.presign_get(receipt_key)
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read()
            s3_ok = resp.status == 200 and data[:4] == b"%PDF" and len(data) > 500
        n_email = db.execute(select(func.count()).select_from(Notification).where(
            Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one()

        print(f"1. amount {pay.amount} == enrollment.final_fee {final_fee}: {'✅' if a_amount else '❌'}")
        print(f"2. payment paid + paid_at: {pay.status}/{pay.paid_at is not None} {'✅' if a_paid else '❌'}")
        print(f"3. receipt fetched from S3 (pre-signed GET, real PDF bytes): {'✅' if s3_ok else '❌'}")
        print(f"4. enrollment offered→active, payment_status=paid, payment_id set: {'✅' if a_enr else '❌'}")
        print(f"5. confirmation email in ledger: n={n_email} {'✅' if n_email == 1 else '❌'}")

        # ── (i) double-confirm the SAME payment → no-op ──
        paid_at_1 = pay.paid_at
        confirm_payment(enrollment_id=enr.id, ctx=ctx, db=db)
        db.expire_all()
        n_pay = db.execute(select(func.count()).select_from(Payment).where(
            Payment.enrollment_id == enr.id)).scalar_one()
        pay2 = db.execute(select(Payment).where(Payment.enrollment_id == enr.id)).scalar_one()
        n_email2 = db.execute(select(func.count()).select_from(Notification).where(
            Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one()
        a_redeliver = n_pay == 1 and pay2.paid_at == paid_at_1 and n_email2 == 1
        print(f"6. double-confirm no-op: 1 payment row, same paid_at, 1 email: {'✅' if a_redeliver else '❌'}")

        # ── (ii) wrong-state: a distinct unpaid P2 against the now-active enrolment → 409 ──
        from fastapi import HTTPException
        p2 = Payment(tenant_id=tid, business_unit_id="ACADEMY", enrollment_id=enr.id,
                     amount=final_fee, currency="INR", status="created", provider="stub")
        db.add(p2); db.commit()
        got_409 = False
        try:
            confirm_payment(enrollment_id=enr.id, ctx=ctx, db=db)
        except HTTPException as e:
            got_409 = e.status_code == 409 and e.detail.get("code") == "STATUS_INVALID"
            db.rollback()
        db.expire_all()
        p2_still_open = db.execute(select(Payment.status).where(Payment.id == p2.id)).scalar_one() == "created"
        a_conflict = got_409 and p2_still_open
        print(f"7. second-payment conflict → 409, P2 stays 'created' (nothing activated): "
              f"{'✅' if a_conflict else '❌'}")

        ok = all([a_amount, a_paid, s3_ok, a_enr, n_email == 1, a_redeliver, a_conflict])
    finally:
        db.rollback()
        db.execute(delete(Notification).where(Notification.tenant_id == tid,
                   Notification.template_code == "academy_enrolment_active"))
        db.execute(delete(Payment).where(Payment.tenant_id == tid, Payment.business_unit_id == "ACADEMY",
                   Payment.enrollment_id.in_(select(Enrollment.id).where(
                       Enrollment.tenant_id == tid, Enrollment.business_unit_id == "ACADEMY"))))
        db.execute(delete(Test).where(Test.tenant_id == tid, Test.business_unit_id == "ACADEMY"))
        for e in made:
            db.execute(delete(type(e)).where(type(e).id == e.id))
        db.commit(); db.close()
        if receipt_key:
            try:
                storage._client().delete_object(Bucket=storage.settings.storage_bucket, Key=receipt_key)
                print("8. probe rows + S3 receipt object cleaned")
            except Exception as ex:  # noqa: BLE001
                print(f"8. rows cleaned; S3 receipt delete warning: {ex}")
        else:
            print("8. probe rows cleaned")
    print("A6 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
