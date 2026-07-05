"""Reconciliation dev probe (FE#4/#4b + MinIO storage-split blast-radius) — sps_app.

A. STAFFING S3 blast-radius: with the presign-split code DEPLOYED and both s3
   endpoint envs UNSET on dev, a real staffing S3 round-trip (presign_put → PUT →
   presign_get → GET) still works and hits the real bucket — proving the split is
   inert for the EXISTING vertical, not just for academy.

B. Academy chain on real RDS: issue → aptitude-invite notification lands →
   /students/me/notifications returns it WITH take_link → take → submit →
   /students/me/enrollments reflects offered+score+discount+final_fee AND stays
   tokenless. LOAD-BEARING isolation on real data: student B's session cannot read
   A's notifications or A's live take token.

FLAG: FEATURE_ACADEMY is flipped `settings.feature_academy = True` IN THIS PROBE
PROCESS ONLY (a one-off ECS task). The running service's task-def is untouched —
it stays FEATURE_ACADEMY=False. When this task exits, nothing persists; no revert
step is needed because nothing in the service was changed. Self-cleans all rows.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
import uuid

from sqlalchemy import delete, select, text

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app import storage
from app.academy_deps import StudentContext
from app.models import Notification
from app.models_academy import Cohort, Course, Enrollment, Student
from app.models_staffing import Test


def _put(url: str, data: bytes, content_type: str) -> int:
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type": content_type})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read()


def leg_a(db) -> bool:
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    key = f"tenant={tid}/business_unit=STAFFING/_probe/{uuid.uuid4()}.txt"
    payload = b"reconcile-probe-staffing-blast-radius"
    put_url = storage.presign_put(key, "text/plain")
    host_ok = put_url.startswith(f"https://{settings.storage_bucket}.s3.") and "localhost:9000" not in put_url
    put_code = _put(put_url, payload, "text/plain")
    got = _get(storage.presign_get(key))
    storage.delete_object(key)                       # clean
    ok = host_ok and put_code in (200, 204) and got == payload
    print(f"A. STAFFING S3 round-trip on dev (presign-split deployed, envs unset): "
          f"virtual-host real-S3 URL={host_ok}, PUT={put_code}, GET-bytes-match={got == payload} "
          f"{'✅' if ok else '❌'}")
    return ok


def leg_b(db) -> bool:
    settings.feature_academy = True                  # IN-PROCESS ONLY (this task); service stays off
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import issue_aptitude, my_enrollments, my_notifications
    from app.routers.take import fetch_paper, submit_answers, SubmitIn
    made: list = []
    ok = False
    try:
        def mk(tag):
            s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name=f"Rec {tag}",
                        email=f"recprobe-{tag}-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
            db.add(s); db.flush(); made.append(s)
            c = Course(tenant_id=tid, business_unit_id="ACADEMY", title=f"Rec {tag}",
                       slug=f"rec-{uuid.uuid4().hex[:8]}", fee=50000)
            db.add(c); db.flush(); made.append(c)
            co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id, name="B")
            db.add(co); db.flush(); made.append(co)
            e = Enrollment(tenant_id=tid, business_unit_id="ACADEMY", cohort_id=co.id,
                           student_id=s.id, course_id=c.id, status="applied")
            db.add(e); db.flush(); made.append(e)
            return s, e

        a, ea = mk("A"); b, eb = mk("B")
        db.commit()
        ctxA = StudentContext(student_id=a.id, tenant_id=str(tid), email=a.email, college_student_id=None)
        ctxB = StudentContext(student_id=b.id, tenant_id=str(tid), email=b.email, college_student_id=None)
        staff = RequestContext(tenant_id=str(tid), business_unit_id="ACADEMY", user_id=None, roles=("recruiter",))

        # issue for A and B (each gets their own invite)
        issue_aptitude(enrollment_id=ea.id, ctx=staff, db=db, idempotency_key=None)
        issue_aptitude(enrollment_id=eb.id, ctx=staff, db=db, idempotency_key=None)

        # A's notifications carry A's invite + take_link
        na = my_notifications(student=ctxA, db=db)
        inv = [n for n in na if n["template_code"] == "academy_aptitude_invite" and n["take_link"]]
        a_link = inv[0]["take_link"] if inv else None
        a_token = a_link.rsplit("/", 1)[-1] if a_link else None
        r_invite = len(inv) == 1 and a_token is not None
        print(f"1. issue → A's /me/notifications returns the invite WITH take_link: {'✅' if r_invite else '❌'}")

        # ISOLATION on real RDS: B's session sees neither A's notification nor A's live token
        import json
        nb = my_notifications(student=ctxB, db=db)
        blob = json.dumps(nb)
        r_iso = (a_token not in blob) and (a.email not in blob) and all(
            n["take_link"] != a_link for n in nb)
        print(f"2. ISOLATION: B's session cannot read A's notification or A's live token: {'✅' if r_iso else '❌'}")

        # take + submit A's test (all correct)
        t = db.execute(select(Test).where(Test.enrollment_id == ea.id)).scalar_one()
        fetch_paper(token=a_token, db=db)
        sub = submit_answers(token=a_token, body=SubmitIn(
            answers={f["qid"]: f["correct"] for f in t.served_questions}), db=db)
        r_submit = round(sub["score"] * 100, 1) == 100.0

        # A's enrollments reflect the result AND stay tokenless
        ea_rows = my_enrollments(student=ctxA, db=db)
        row = ea_rows[0]
        r_reflect = (row["status"] == "offered" and float(row["aptitude_score"]) == 100.0
                     and int(row["discount_percent"]) == 20 and float(row["final_fee"]) == 40000.0)
        r_tokenless = a_token not in json.dumps(ea_rows)
        print(f"3. take+submit ({round(sub['score']*100)}%) → A's /me/enrollments: status={row['status']} "
              f"score={row['aptitude_score']} discount={row['discount_percent']} fee={row['final_fee']} "
              f"{'✅' if r_reflect else '❌'}")
        print(f"4. enrollments read stays TOKENLESS on real RDS: {'✅' if r_tokenless else '❌'}")
        ok = all([r_invite, r_iso, r_submit, r_reflect, r_tokenless])
    finally:
        db.rollback()
        db.execute(delete(Notification).where(Notification.recipient.like("recprobe-%")))
        # tests reference enrollments (FK) → delete them first
        enr_ids = [o.id for o in made if isinstance(o, Enrollment)]
        if enr_ids:
            db.execute(delete(Test).where(Test.enrollment_id.in_(enr_ids)))
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("5. probe rows cleaned")
    return ok


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    a = leg_a(db)
    b = leg_b(db)
    db.close()
    print("RECONCILE PROBE: " + ("PASS" if (a and b) else "FAIL"))
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(main())
