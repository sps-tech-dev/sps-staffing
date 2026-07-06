"""FE#7 (B) durable receipt — dev probe on real RDS. sps_app.

1. A genuinely #6-paid enrolment (paid via _activate_payment → receipt_s3_key set)
   → GET .../receipt → 200 receipt_url → the presigned GET fetches real %PDF bytes
   from real S3 (first time the receipt read hits real S3 — local was MinIO).
2. has_receipt on real data: that enrolment → true; a paid-but-null-receipt row → false.
3. ISOLATION: A → B's enrolment id = 404 NOT_FOUND, no receipt_url; a nonexistent id
   = identical 404 (no existence oracle).
4. Own unpaid → 404 RECEIPT_NOT_AVAILABLE.

Flag flipped `settings.feature_academy=True` IN THIS PROBE PROCESS ONLY (one-off
task); the live task-def is untouched → stays OFF. Self-cleans rows + the S3 object.
"""
from __future__ import annotations

import sys
import urllib.request
import uuid

from sqlalchemy import delete, func, select, text

from app.config import settings
from app.context import RequestContext
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
    from app.routers.academy import student_pay, student_receipt, my_enrollments
    made: list = []
    receipt_key = None
    ok = False
    try:
        def mk(tag, status="offered", final=40000.0):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"Rcpt {tag}",
                        email=f"rcptprobe-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title=f"Rcpt {tag}",
                       slug=f"rcpt-{uuid.uuid4().hex[:8]}", fee=50000)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="B")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status=status,
                           aptitude_score=96, discount_percent=20, final_fee=final)
            db.add(e); db.flush(); made.append(e)
            return s, e

        # A: genuine #6-paid (via _activate_payment → receipt_s3_key set)
        a, ea = mk("A")
        # B: another paid+receipted student (isolation target)
        b, eb = mk("B")
        # N: paid but receipt_s3_key NULL (direct insert, the has_receipt=false gap)
        n, en = mk("N", status="active")
        # U: unpaid own enrolment
        u, eu = mk("U")
        db.commit()
        ctxA = StudentContext(student_id=a.id, tenant_id=str(tid), email=a.email, college_student_id=None)
        ctxB = StudentContext(student_id=b.id, tenant_id=str(tid), email=b.email, college_student_id=None)
        ctxN = StudentContext(student_id=n.id, tenant_id=str(tid), email=n.email, college_student_id=None)
        ctxU = StudentContext(student_id=u.id, tenant_id=str(tid), email=u.email, college_student_id=None)

        # activate A and B through the real pay seam (generates real S3 receipts)
        student_pay(enrollment_id=ea.id, student=ctxA, db=db)
        student_pay(enrollment_id=eb.id, student=ctxB, db=db)
        # N: a direct-insert paid Payment with NO receipt_s3_key
        db.add(Payment(tenant_id=tid, business_unit_id="ACADEMY", enrollment_id=en.id,
                       amount=40000, currency="INR", status="paid", provider="stub"))
        en.payment_status = "paid"; db.commit()
        payA = db.execute(select(Payment).where(Payment.enrollment_id == ea.id)).scalar_one()
        receipt_key = payA.receipt_s3_key
        payB = db.execute(select(Payment).where(Payment.enrollment_id == eb.id)).scalar_one()
        receipt_key_b = payB.receipt_s3_key   # capture as a STRING (payB is deleted in the finally)

        # 1. own receipt → 200 → fetch real %PDF from real S3
        res = student_receipt(enrollment_id=ea.id, student=ctxA, db=db)
        with urllib.request.urlopen(res["receipt_url"], timeout=20) as r:
            data = r.read()
        a1 = r.status == 200 and data[:4] == b"%PDF" and len(data) > 500
        print(f"1. own receipt: presigned GET → {r.status}, %PDF={data[:4]==b'%PDF'}, {len(data)}B {'✅' if a1 else '❌'}")

        # 2. has_receipt on real data
        ha = my_enrollments(student=ctxA, db=db)[0]["has_receipt"]
        hn = my_enrollments(student=ctxN, db=db)[0]["has_receipt"]
        a2 = ha is True and hn is False
        print(f"2. has_receipt: receipted={ha} (true) | paid-null-receipt={hn} (false) {'✅' if a2 else '❌'}")

        # 3. ISOLATION: A → B's enrolment = 404 NOT_FOUND; nonexistent id = same
        from fastapi import HTTPException
        def code_for(ctx, enr_id):
            try:
                student_receipt(enrollment_id=enr_id, student=ctx, db=db); return "200-LEAK"
            except HTTPException as ex:
                return ex.detail.get("code")
        c_b = code_for(ctxA, eb.id)
        c_x = code_for(ctxA, uuid.uuid4())
        a3 = c_b == "NOT_FOUND" and c_x == "NOT_FOUND"
        print(f"3. ISOLATION: A→B's receipt={c_b} | nonexistent={c_x} (both NOT_FOUND, B unobtainable) {'✅' if a3 else '❌'}")

        # 4. own unpaid → RECEIPT_NOT_AVAILABLE
        c_u = code_for(ctxU, eu.id)
        a4 = c_u == "RECEIPT_NOT_AVAILABLE"
        print(f"4. own unpaid → {c_u} {'✅' if a4 else '❌'}")

        ok = all([a1, a2, a3, a4])
    finally:
        db.rollback()
        db.execute(delete(Notification).where(Notification.recipient.like("rcptprobe-%")))
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        if enr_ids:
            db.execute(delete(Payment).where(Payment.enrollment_id.in_(enr_ids)))
        for obj in reversed(made):
            if not isinstance(obj, Payment):
                db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        # delete both real S3 receipt objects
        for key in {receipt_key, locals().get("receipt_key_b")}:
            if key:
                try:
                    storage._client().delete_object(Bucket=storage.settings.storage_bucket, Key=key)
                except Exception:  # noqa: BLE001
                    pass
        print("5. probe rows + S3 receipt objects cleaned")
    print("FE#7 RECEIPT PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
