"""8b-3 fee-waive — dev probe on real RDS. sps_app. Proves: a waiver = activation
WITHOUT money (NO Payment row, NO receipt, payment_status='waived'); coherence
(has_receipt false, receipt endpoint 404); the PAYMENT path still works on real
infra (Payment + real %PDF receipt bytes from S3 + both audits) — i.e. the seam
split didn't break the money path; and the one-entry-point invariant (manual
→active still 409). Flag flipped in-process only; live task-def untouched.
Self-cleans ENTITY rows + the payment S3 receipt by own ids; audit rows persist.
"""
from __future__ import annotations

import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select, text

from app.academy_deps import StudentContext
from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import AuditLog, Notification
from app.models_academy import Cohort, Course, Enrollment, Payment, Student

TRANSITION = "academy.enrollment.transition"
FEE_WAIVED = "academy.enrolment.fee_waived"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import (WaiveIn, StatusMoveIn, waive_enrollment,
                                     move_enrollment_status, student_pay, student_receipt, my_enrollments)
    made: list = []
    staff_uid = uuid.uuid4()
    receipt_key = None
    ok = False
    try:
        def enrol(status="offered"):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Waive Probe",
                        email=f"waiveprobe-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title="Waive Probe",
                       slug=f"waive-{uuid.uuid4().hex[:8]}", fee=50000)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="Probe")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status=status,
                           aptitude_score=70, discount_percent=0, final_fee=50000)
            db.add(e); db.flush(); made.append(e); db.commit()
            return s, e

        staff = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY",
                               user_id=str(staff_uid), roles=("recruiter",), client_id=None)

        def aud(enr_id, action):
            return db.execute(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == enr_id)).scalars().all()

        # 1. WAIVER on real RDS
        sw, ew = enrol("offered")
        reason = "probe: fee waived — merit"
        res = waive_enrollment(enrollment_id=ew.id, body=WaiveIn(reason=reason), ctx=staff, db=db)
        db.refresh(ew)
        pays = db.execute(select(Payment).where(Payment.enrollment_id == ew.id)).scalars().all()
        ta, fw = aud(ew.id, TRANSITION), aud(ew.id, FEE_WAIVED)
        notif = db.execute(select(Notification).where(Notification.idempotency_key == f"academy:fee_waived:{ew.id}")).scalar_one_or_none()
        a1 = (res["status"] == "active" and res["payment_status"] == "waived"
              and ew.status == "active" and ew.payment_status == "waived" and ew.payment_id is None
              and len(pays) == 0 and len(ta) == 1 and ta[0].after["to"] == "active" and ta[0].after["kind"] == "system"
              and len(fw) == 1 and fw[0].after["reason"] == reason and fw[0].after["actor"] == str(staff_uid) and fw[0].actor_id == staff_uid
              and notif is not None and notif.template_code == "academy_enrolment_waived")
        print(f"1. WAIVER: status={ew.status} payment_status={ew.payment_status} payment_id={ew.payment_id} "
              f"Payment_rows={len(pays)} (0), transition_audit={len(ta)} fee_waived_audit={len(fw)} "
              f"actor={fw[0].after['actor'] if fw else None}(==staff {staff_uid}) email={notif.template_code if notif else None}: {'✅' if a1 else '❌'}")

        # 2. WAIVED coherence: has_receipt false + receipt endpoint 404
        me = my_enrollments(student=StudentContext(student_id=sw.id, tenant_id=str(tid), email=sw.email, college_student_id=None), db=db)
        row = next((r for r in me if r["enrollment_id"] == str(ew.id)), None)
        got_404 = False
        try:
            student_receipt(enrollment_id=ew.id,
                            student=StudentContext(student_id=sw.id, tenant_id=str(tid), email=sw.email, college_student_id=None), db=db)
        except HTTPException as ex:
            got_404 = ex.status_code == 404 and ex.detail.get("code") == "RECEIPT_NOT_AVAILABLE"
        a2 = row is not None and row["has_receipt"] is False and got_404
        print(f"2. WAIVED coherence: has_receipt={row['has_receipt'] if row else None} (False), "
              f"receipt endpoint → 404 RECEIPT_NOT_AVAILABLE={got_404}: {'✅' if a2 else '❌'}")

        # 3. PAYMENT PATH STILL WORKS (the refactor is transparent on real infra)
        sp, ep = enrol("offered")
        student_pay(enrollment_id=ep.id, student=StudentContext(student_id=sp.id, tenant_id=str(tid), email=sp.email, college_student_id=None), db=db)
        db.refresh(ep)
        pay = db.execute(select(Payment).where(Payment.enrollment_id == ep.id)).scalar_one()
        receipt_key = pay.receipt_s3_key
        from app import storage
        pdf_bytes = storage._client().get_object(Bucket=storage.settings.storage_bucket, Key=pay.receipt_s3_key)["Body"].read()
        pnotif = db.execute(select(Notification).where(Notification.idempotency_key == f"academy:payment_confirmed:{pay.id}")).scalar_one_or_none()
        pta = aud(ep.id, TRANSITION)
        ppa = db.execute(select(AuditLog).where(AuditLog.action == "academy.payment_activate", AuditLog.entity_id == pay.id)).scalars().all()
        a3 = (ep.status == "active" and ep.payment_status == "paid" and pay.status == "paid"
              and pdf_bytes[:5] == b"%PDF-" and pnotif is not None and pnotif.template_code == "academy_enrolment_active"
              and len(pta) == 1 and len(ppa) == 1)
        print(f"3. PAYMENT PATH: status={ep.status} payment_status={ep.payment_status} Payment.status={pay.status} "
              f"receipt_bytes={pdf_bytes[:5]} email={pnotif.template_code if pnotif else None} "
              f"transition_audit={len(pta)} payment_activate_audit={len(ppa)}: {'✅' if a3 else '❌'}")

        # 4. one-entry-point: a manual →active still 409 (8b-2 unchanged)
        _, em = enrol("offered")
        got_409 = False
        try:
            move_enrollment_status(enrollment_id=em.id, body=StatusMoveIn(to_state="active", reason="force"), ctx=staff, db=db)
        except HTTPException as ex:
            got_409 = ex.status_code == 409; db.rollback()
        db.refresh(em)
        a4 = got_409 and em.status == "offered"
        print(f"4. one-entry-point: manual →active → {409 if got_409 else '???'}, status={em.status} (unchanged): {'✅' if a4 else '❌'}")

        ok = all([a1, a2, a3, a4])
    finally:
        db.rollback()
        # ENTITY rows + the payment S3 receipt only. AUDIT rows persist (append-only).
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        if enr_ids:
            db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
        db.execute(delete(Notification).where(Notification.recipient.like("waiveprobe-%")))
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        if receipt_key:
            try:
                from app import storage
                storage._client().delete_object(Bucket=storage.settings.storage_bucket, Key=receipt_key)
            except Exception:  # noqa: BLE001
                pass
        print("5. ENTITY rows + payment S3 receipt cleaned by own ids (audit rows persist — append-only)")
    print("8b-3 WAIVE PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
