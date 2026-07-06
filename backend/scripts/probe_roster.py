"""FE#8a admin roster — dev probe on real RDS. sps_app. Exercises the FULL gate
chain (require_feature + get_current_context + _require_staff) via TestClient
against the deployed code + real RDS, using FORGED tokens (dev has no activated
staff login). The GATE is load-bearing.

  1. staff → GET /enrollments lists in-tenant ACADEMY, UNMASKED, phone_enc/pan_enc ABSENT.
  2. flag-off → 404 (require_feature), toggled in-process.
  3. a STUDENT academy token → 401 (student cookie ≠ staff session).
  4. a bound CLIENT session → 403 (no cross-client leak).
  5. tenant isolation: dev is single-tenant — NOT mutating shared.tenants on real RDS;
     covered end-to-end by the unit test (which builds a real 2nd tenant). Stated.

Flag flipped in-process only; live task-def untouched (confirm OFF after). Self-cleans
the probe's OWN rows by id.
"""
from __future__ import annotations

import sys
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.config import settings
from app.db import get_sessionmaker
from app.main import app
from app.models_academy import Cohort, Course, Enrollment, Student
from app.security import create_access_token, create_academy_token

HOST = {"host": "spstechnosoft.com"}
EP = "/api/academy/enrollments"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    made: list = []
    ok = False
    try:
        # a probe enrolment under SPS001 / ACADEMY, with real (unmasked) + encrypted PII
        s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Roster Probe",
                    email=f"rosterprobe-{uuid.uuid4().hex[:6]}@local.test",
                    student_id="COLL-PROBE", college_name="Probe College",
                    phone_enc="9811100099", password_hash="x")
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

        staff_tok = create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(tid),
                                         "role_flat": ["recruiter"]})
        staff = TestClient(app); staff.cookies.set("access_token", staff_tok)

        # 1. staff → 200, probe enrolment present, unmasked, NO phone/pan on real data
        settings.feature_academy = True
        r = staff.get(EP, headers=HOST)
        rows = r.json() if r.status_code == 200 else []
        row = next((x for x in rows if x["enrollment_id"] == str(e.id)), None)
        import json
        blob = json.dumps(row or {})
        a1 = (r.status_code == 200 and row is not None
              and row["student"]["full_name"] == "Roster Probe"
              and row["student"]["email"] == s.email
              and "9811100099" not in blob and "phone" not in blob.lower() and "pan" not in blob.lower())
        print(f"1. staff GET /enrollments: {r.status_code}, probe enrolment present, unmasked "
              f"(name/email), phone_enc/pan_enc ABSENT: {'✅' if a1 else '❌'}")
        d = staff.get(f"{EP}/{e.id}", headers=HOST)
        a1b = d.status_code == 200 and "9811100099" not in d.text and "payment" in d.json()
        print(f"   detail GET /{{'{'}}id{{'}'}}: {d.status_code}, phone absent, payment block present: {'✅' if a1b else '❌'}")

        # 2. flag-off → 404 (require_feature)
        settings.feature_academy = False
        r404 = staff.get(EP, headers=HOST)
        a2 = r404.status_code == 404
        settings.feature_academy = True
        print(f"2. flag-off → {r404.status_code} (expect 404): {'✅' if a2 else '❌'}")

        # 3. a STUDENT academy token → 401 (no access_token)
        acad_tok = create_academy_token({"sub": str(s.id), "tenant_id": str(tid),
                                         "kind": "academy_student", "role": "student", "email": s.email})
        stu = TestClient(app); stu.cookies.set("academy_access_token", acad_tok)
        r_stu = stu.get(EP, headers=HOST)
        a3 = r_stu.status_code == 401
        print(f"3. student academy token → {r_stu.status_code} (expect 401): {'✅' if a3 else '❌'}")

        # 4. a bound CLIENT session → 403
        cli_tok = create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(tid),
                                       "role_flat": ["client"], "client_id": str(uuid.uuid4())})
        cli = TestClient(app); cli.cookies.set("access_token", cli_tok)
        r_cli = cli.get(EP, headers=HOST)
        a4 = r_cli.status_code == 403
        print(f"4. bound CLIENT session → {r_cli.status_code} (expect 403, no cross-client leak): {'✅' if a4 else '❌'}")

        # 5. tenant isolation — stated, not mutated on dev
        print("5. tenant isolation: dev single-tenant — NOT mutating shared.tenants on real RDS; "
              "covered end-to-end by the unit test (builds a real 2nd tenant). ✅ (by unit test)")

        ok = all([a1, a1b, a2, a3, a4])
    finally:
        db.rollback()
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("6. probe rows cleaned (by own id)")
    print("FE#8a ROSTER PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
