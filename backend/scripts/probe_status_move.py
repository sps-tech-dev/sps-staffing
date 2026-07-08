"""8b-2 manual status-move — dev probe on real RDS. sps_app. Calls the endpoint
FUNCTION directly with a forged staff ctx (dev has no activated staff login; the
prod image has no TestClient — the 8a lesson). Proves the manual move + STAFF
attribution, and that the endpoint delegates the →active block to the machine on
real data. Flag flipped in-process only; live task-def untouched.
"""
from __future__ import annotations

import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import AuditLog
from app.models_academy import Cohort, Course, Enrollment, Student

TRANSITION = "academy.enrollment.transition"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import move_enrollment_status, StatusMoveIn
    made: list = []
    staff_uid = uuid.uuid4()                          # the (forged) staff user — the attribution subject
    ok = False
    try:
        def enrol(status="offered"):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Move Probe",
                        email=f"moveprobe-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title="Move Probe",
                       slug=f"move-{uuid.uuid4().hex[:8]}", fee=50000)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="Probe")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status=status)
            db.add(e); db.flush(); made.append(e); db.commit()
            return e

        staff = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY",
                               user_id=str(staff_uid), roles=("recruiter",), client_id=None)

        def audits(enr_id):
            return db.execute(select(AuditLog).where(
                AuditLog.action == TRANSITION, AuditLog.entity_id == enr_id)
                .order_by(AuditLog.id)).scalars().all()

        # 1. manual offered→cancelled with reason → status + audit attributed to the STAFF user
        e = enrol("offered")
        reason = "probe: manual cancel"
        res = move_enrollment_status(enrollment_id=e.id,
                                     body=StatusMoveIn(to_state="cancelled", reason=reason),
                                     ctx=staff, db=db)
        db.refresh(e)
        a = audits(e.id)
        row = a[-1] if a else None
        a1 = (res["status"] == "cancelled" and e.status == "cancelled" and len(a) == 1
              and row.after["from"] == "offered" and row.after["to"] == "cancelled"
              and row.after["kind"] == "manual" and row.after["reason"] == reason
              and row.after["actor"] == str(staff_uid) and row.actor_id == staff_uid)
        print(f"1. manual offered→cancelled: status={e.status}, audit "
              f"{row.after['from']}→{row.after['to']} kind={row.after['kind']} "
              f"actor={row.after['actor']} (== staff user {staff_uid}) actor_id_match={row.actor_id == staff_uid} "
              f"{'✅' if a1 else '❌'}")

        # 2. delegation: manual →active → 409, status UNCHANGED, NO audit row
        e2 = enrol("offered")
        got_409 = False
        try:
            move_enrollment_status(enrollment_id=e2.id, body=StatusMoveIn(to_state="active", reason="force"),
                                   ctx=staff, db=db)
        except HTTPException as ex:
            got_409 = ex.status_code == 409
            db.rollback()
        db.refresh(e2)
        a2 = got_409 and e2.status == "offered" and len(audits(e2.id)) == 0
        print(f"2. manual →active → {409 if got_409 else '???'}, status={e2.status} (unchanged), "
              f"audit rows for rejected move={len(audits(e2.id))} (0): {'✅' if a2 else '❌'}")

        # 3. endpoint's own two checks: missing reason → 422; garbage to_state → 422
        e3 = enrol("offered")
        def code_for(to_state, reason):
            try:
                move_enrollment_status(enrollment_id=e3.id, body=StatusMoveIn(to_state=to_state, reason=reason),
                                       ctx=staff, db=db); return None
            except HTTPException as ex:
                db.rollback(); return (ex.status_code, ex.detail.get("code"))
        no_reason = code_for("cancelled", None)
        garbage = code_for("banana", "x")
        a3 = no_reason == (422, "REASON_REQUIRED") and garbage == (422, "VALIDATION_ERROR")
        print(f"3. missing reason → {no_reason}; garbage to_state → {garbage}: {'✅' if a3 else '❌'}")

        # 4. tenant isolation — not manufactured on dev (single-tenant); covered by the unit test
        print("4. tenant isolation: dev single-tenant — NOT manufacturing a 2nd tenant on real RDS; "
              "covered end-to-end by the unit test (real 2nd tenant). ✅ (by unit test)")

        ok = all([a1, a2, a3])
    finally:
        db.rollback()
        # ENTITY rows only. The academy.enrollment.transition AUDIT rows PERSIST
        # (append-only, correct — an audit trail outlives its entities); not deleted.
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("5. probe ENTITY rows cleaned by own id (transition audit rows persist — append-only)")
    print("8b-2 STATUS-MOVE PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
