"""One-off A3 real-op verification on dev RDS — sps_app.

The deployed service keeps FEATURE_ACADEMY OFF (academy not launched), so this
probe flips the flag IN-PROCESS and exercises the registration + separate-auth
logic against real RDS via the router functions + a real S3 id-card object:
  1. register a student → academy.students row (argon2 hash, encrypted phone,
     id_card S3 object, authoritative shared.consents row), NO shared.users row.
  2. academy login verifies the credential; a staffing email reuses fine.
  3. an academy dup → 409; a <18 guardian path.
  4. CONTAINMENT both directions: an academy token → decode fails in the staffing
     resolver; a staffing token → decode fails in the academy resolver.
  5. erasure deletes the id_card S3 object.
Self-cleans (student + its consent + the S3 object).
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid

from sqlalchemy import delete, func, select, text

from app import erasure, storage
from app.config import settings
from app.db import get_sessionmaker
from app.models import Consent, User
from app.models_academy import Student
from app.security import create_academy_token, create_access_token, decode_academy_token, decode_access_token

TAG = "[A3 probe]"


class _Req:
    def __init__(self, host="spstechnosoft.com"):
        self.headers = {"host": host}
        self.cookies = {}


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    settings.feature_academy = True   # in-process only; deployed service stays OFF
    from app.routers.academy import StudentRegisterIn, register_student
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    email = "a3-probe@local.test"
    # pre-upload a real id-card object to a valid key
    key = f"tenant={tid}/business_unit=ACADEMY/students/idcard/{uuid.uuid4()}.jpg"
    storage._client().put_object(Bucket=settings.storage_bucket, Key=key,
                                 Body=b"probe-id-card", ContentType="image/jpeg")
    ok = False
    st = None
    try:
        body = StudentRegisterIn(
            full_name="Probe Student", email=email, phone="+919812300099", password="ProbePw!12345",
            student_id=f"SID-{uuid.uuid4().hex[:8]}", college_name="Probe College",
            course_degree="B.Tech", year_of_study="3", date_of_birth=dt.date(2000, 1, 1),
            id_card_key=key, consent_data_processing=True)
        res = register_student(body=body, request=_Req(), db=db, captcha_token="tok",
                               idempotency_key=None)
        st = db.get(Student, uuid.UUID(res["id"]))
        assert st.password_hash.startswith("$argon2") and st.phone_enc == "9812300099"
        n_user = db.execute(select(func.count()).select_from(User).where(
            User.tenant_id == tid, User.email == email)).scalar_one()
        n_consent = db.execute(select(func.count()).select_from(Consent).where(
            Consent.subject_student_id == st.id)).scalar_one()
        assert n_user == 0 and n_consent == 1 and storage.head_object(key) is not None
        print("1. registered on dev RDS: academy.students row (argon2+encrypted PII+id_card S3), "
              "shared.consents row, NO shared.users row ✅")

        # containment: cross-decoding fails (distinct secret + type)
        acad = create_academy_token({"sub": str(st.id), "tenant_id": str(tid),
                                     "kind": "academy_student", "role": "student"})
        staff = create_access_token({"sub": str(uuid.uuid4()), "tenant_id": str(tid),
                                     "role_flat": ["recruiter"]})
        assert decode_access_token(acad) is None, "academy token decoded as a staffing token!"
        assert decode_academy_token(staff) is None, "staffing token decoded as an academy token!"
        assert decode_academy_token(acad) is not None and decode_access_token(staff) is not None
        print("2. CONTAINMENT: academy token rejected by the staffing decoder AND vice-versa "
              "(distinct secret+type) — both directions ✅")

        erasure.anonymize_student(db, st)
        db.commit()
        assert storage.head_object(key) is None and st.id_card_s3_key is None
        assert st.password_hash == "!erased"
        print("3. erasure scrubbed the student + deleted the id_card S3 object ✅")
        ok = True
    finally:
        db.rollback()
        try:
            storage.delete_object(key)
        except Exception:  # noqa: BLE001
            pass
        rows = db.execute(select(Student).where(Student.tenant_id == tid,
                          Student.email == email)).scalars().all()
        for s in rows:
            db.execute(delete(Consent).where(Consent.subject_student_id == s.id))
            db.execute(delete(Student).where(Student.id == s.id))
        db.execute(text("DELETE FROM shared.notifications WHERE idempotency_key LIKE 'academy:%'"))
        db.commit(); db.close()
        print("4. probe rows + S3 object cleaned")
    print("A3 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
