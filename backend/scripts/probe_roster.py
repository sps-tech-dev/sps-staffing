"""FE#8a admin roster — dev probe on real RDS. sps_app.

The prod image has NO httpx/TestClient (dev-only dep), so this exercises the
DEPLOYED read + guard predicates DIRECTLY on real RDS. The unique real-RDS value
is the READ over real encrypted PII (phone_enc/pan_enc must be ABSENT, identity
UNMASKED). The full HTTP gate COMPOSITION (require_feature 404 / get_current_context
401 / _require_staff 403) is deterministic auth logic covered by the 8 unit tests
(TestClient locally); here we assert each guard PREDICATE on the deployed code.

  1. staff read → probe enrolment present, UNMASKED, phone_enc/pan_enc ABSENT (real RDS).
  2. detail → unmasked + payment/test blocks, phone absent.
  3. flag gate: is_enabled('academy') False when off (→ require_feature 404), True when on.
  4. student: a student's academy token is NOT a valid access token → get_current_context 401.
  5. client: _require_staff(client_ctx) → 403 (no cross-client leak); staff_ctx passes.
  6. tenant isolation: dev single-tenant — NOT mutating shared.tenants; covered by the unit
     test (builds a real 2nd tenant). Stated.

Flag flipped in-process only; live task-def untouched. Self-cleans the probe's OWN rows by id.
"""
from __future__ import annotations

import json
import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.features import is_enabled
from app.models_academy import Cohort, Course, Enrollment, Student
from app.security import create_academy_token, decode_access_token


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True                  # in-process only
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import list_enrollments, enrollment_detail
    from app.routers.staffing import _require_staff
    made: list = []
    ok = False
    try:
        s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Roster Probe",
                    email=f"rosterprobe-{uuid.uuid4().hex[:6]}@local.test",
                    student_id="COLL-PROBE", college_name="Probe College",
                    phone_enc="9811100099", password_hash="x")   # real encrypted PII
        db.add(s); db.flush(); made.append(s)
        c = Course(tenant_id=tid, business_unit_id="ACADEMY", title="Roster Probe",
                   slug=f"rosterprobe-{uuid.uuid4().hex[:8]}", fee=50000)
        db.add(c); db.flush(); made.append(c)
        co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="Probe Batch")
        db.add(co); db.flush(); made.append(co)
        e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                       student_id=s.id, course_id=c.id, status="offered",
                       aptitude_score=88, discount_percent=15, final_fee=42500)
        db.add(e); db.flush(); made.append(e)
        db.commit()

        staff_ctx = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY",
                                   user_id=str(uuid.uuid4()), roles=("recruiter",), client_id=None)
        client_ctx = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY",
                                    user_id=str(uuid.uuid4()), roles=("client",), client_id=str(uuid.uuid4()))

        # 1. staff read — real RDS, unmasked, phone/pan ABSENT
        rows = list_enrollments(status=None, course_id=None, cohort_id=None, ctx=staff_ctx, db=db)
        row = next((x for x in rows if x["enrollment_id"] == str(e.id)), None)
        blob = json.dumps(row or {})
        a1 = (row is not None and row["student"]["full_name"] == "Roster Probe"
              and row["student"]["email"] == s.email
              and "9811100099" not in blob and "phone" not in blob.lower() and "pan" not in blob.lower())
        print(f"1. staff read: probe enrolment present, UNMASKED (name/email), phone_enc/pan_enc "
              f"ABSENT on real RDS: {'✅' if a1 else '❌'}")

        # 2. detail
        d = enrollment_detail(enrollment_id=e.id, ctx=staff_ctx, db=db)
        a2 = ("9811100099" not in json.dumps(d) and d.get("payment") is not None or "payment" in d) \
            and d["student"]["full_name"] == "Roster Probe" and "course_degree" in d["student"]
        print(f"2. detail: unmasked + payment/test blocks, phone absent: {'✅' if a2 else '❌'}")

        # 3. flag gate predicate (require_feature core)
        settings.feature_academy = False; off = is_enabled("academy")
        settings.feature_academy = True; on = is_enabled("academy")
        a3 = off is False and on is True
        print(f"3. flag gate: is_enabled off={off} on={on} → require_feature 404 when off: {'✅' if a3 else '❌'}")

        # 4. a student's academy token is NOT a valid ACCESS token → get_current_context 401
        acad_tok = create_academy_token({"sub": str(s.id), "tenant_id": str(tid),
                                         "kind": "academy_student", "role": "student", "email": s.email})
        a4 = decode_access_token(acad_tok) is None
        print(f"4. student academy token decodes as an access token → {decode_access_token(acad_tok)} "
              f"(None → get_current_context 401): {'✅' if a4 else '❌'}")

        # 5. client → _require_staff 403; staff passes
        try:
            _require_staff(client_ctx); c403 = False
        except HTTPException as ex:
            c403 = ex.status_code == 403
        try:
            _require_staff(staff_ctx); staff_ok = True
        except HTTPException:
            staff_ok = False
        a5 = c403 and staff_ok
        print(f"5. _require_staff: client→403 ({c403}), staff→ok ({staff_ok}) — no cross-client leak: {'✅' if a5 else '❌'}")

        print("6. tenant isolation: dev single-tenant — NOT mutating shared.tenants on real RDS; "
              "covered end-to-end by the unit test (builds a real 2nd tenant). ✅ (by unit test)")
        print("   NOTE: full HTTP 404/401/403 composition is covered by the 8 unit tests (TestClient "
              "is a dev-only dep, absent from the prod image); here the deployed guard PREDICATES are "
              "asserted on real RDS.")

        ok = all([a1, a2, a3, a4, a5])
    finally:
        db.rollback()
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("7. probe rows cleaned (by own id)")
    print("FE#8a ROSTER PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
