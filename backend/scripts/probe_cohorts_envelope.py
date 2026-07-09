"""create-2 backend — course_id envelope on the public cohorts read. Dev probe on
real RDS. sps_app. Proves: the {course_id, cohorts} envelope (incl. the empty case),
that the course_id round-trips into apply (the two endpoints compose), and that the
published-only gate still holds. Flag flipped in-process only. Self-cleans by own ids.
"""
from __future__ import annotations

import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select, text
from starlette.requests import Request

from app.academy_deps import StudentContext
from app.config import settings
from app.db import get_sessionmaker
from app.models_academy import Cohort, Course, Enrollment, Student


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who}")
    if who != "sps_app":
        return 1
    settings.feature_academy = True
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    from app.routers.academy import public_course_cohorts, apply_to_course, ApplyIn
    made: list = []
    ok = False

    def course(pub=True, slug=None):
        c = Course(tenant_id=tid, business_unit_id="ACADEMY", title="Envelope Probe",
                   slug=slug or f"env-{uuid.uuid4().hex[:8]}", fee=40000,
                   is_published=pub, status="active" if pub else "draft")
        db.add(c); db.flush(); made.append(c); return c

    def cohort(c, status="open"):
        co = Cohort(tenant_id=tid, business_unit_id="ACADEMY", course_id=c.id,
                    name=f"Batch {status}", status=status, mode="online")
        db.add(co); db.flush(); made.append(co); return co

    def req():
        return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                        "headers": [(b"host", b"spstechnosoft.com")]})

    try:
        # 1. envelope: a published course with open+planned+running cohorts
        c1 = course(pub=True); cohort(c1, "open"); cohort(c1, "planned"); cohort(c1, "running")
        db.commit()
        env = public_course_cohorts(slug=c1.slug, request=req(), db=db)
        statuses = {r["status"] for r in env["cohorts"]}
        a1 = env.get("course_id") == str(c1.id) and statuses == {"open", "planned"}
        print(f"1a. envelope: course_id=={c1.id} → {env.get('course_id')==str(c1.id)}, "
              f"cohorts statuses={statuses} (== {{open,planned}}): {'✅' if a1 else '❌'}")
        # empty-cohorts course → id still carried
        c_empty = course(pub=True); db.commit()
        env2 = public_course_cohorts(slug=c_empty.slug, request=req(), db=db)
        a1b = env2.get("course_id") == str(c_empty.id) and env2.get("cohorts") == []
        print(f"1b. empty-cohorts: {{course_id: {env2.get('course_id')==str(c_empty.id)}, cohorts: {env2.get('cohorts')}}} — id still carried: {'✅' if a1b else '❌'}")

        # 2. round-trip: the course_id FROM the read feeds apply → 201 'applied'
        open_cohort_id = next(r["cohort_id"] for r in env["cohorts"] if r["status"] == "open")
        s = Student(tenant_id=tid, business_unit_id="ACADEMY", full_name="Env Probe",
                    email=f"envprobe-{uuid.uuid4().hex[:6]}@local.test", password_hash="x")
        db.add(s); db.flush(); made.append(s); db.commit()
        created = apply_to_course(
            body=ApplyIn(course_id=uuid.UUID(env["course_id"]), cohort_id=uuid.UUID(open_cohort_id)),
            student=StudentContext(student_id=s.id, tenant_id=str(tid), email=s.email, college_student_id=None), db=db)
        a2 = created["status"] == "applied" and created["course"]["id"] == env["course_id"]
        print(f"2. round-trip: read's course_id → apply → status={created['status']}, "
              f"course.id matches={created['course']['id']==env['course_id']}: {'✅' if a2 else '❌'}")

        # 3. published-only gate still holds
        draft = course(pub=False); cohort(draft, "open"); db.commit()
        got_404 = False
        try:
            public_course_cohorts(slug=draft.slug, request=req(), db=db)
        except HTTPException as ex:
            got_404 = ex.status_code == 404
        print(f"3. unpublished course → {404 if got_404 else '???'} (gate not loosened): {'✅' if got_404 else '❌'}")

        ok = all([a1, a1b, a2, got_404])
    finally:
        db.rollback()
        sids = [o.id for o in made if isinstance(o, Student)]
        if sids:
            db.execute(delete(Enrollment).where(Enrollment.student_id.in_(sids)))
        for obj in reversed(made):
            db.execute(delete(type(obj)).where(type(obj).id == obj.id))
        db.commit()
        print("4. probe rows cleaned by own ids (apply audit rows persist — append-only)")
    print("CREATE-2 ENVELOPE PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
