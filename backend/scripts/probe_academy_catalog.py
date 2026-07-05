"""One-off A2 real-op verification on dev RDS — sps_app.

The deployed service keeps FEATURE_ACADEMY OFF (academy not launched), so this
probe flips the flag IN-PROCESS and exercises the catalog logic against real RDS
via the router functions: publish a seeded course → it appears on the public
surface with SAFE FIELDS ONLY → an unpublished course stays absent → unpublish →
gone. Also asserts the public payload leaks no internal field. Self-cleans
(re-unpublishes the probe course + removes the draft).
"""
from __future__ import annotations

import sys

from sqlalchemy import select, text, update

from app.config import settings
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_academy import Course

TAG = "[A2 probe]"


class _Req:
    headers = {"host": "spstechnosoft.com"}


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    settings.feature_academy = True   # in-process only; the deployed service stays OFF
    from app.routers.academy import (
        CourseIn, PublishIn, create_course, public_courses, publish_course,
    )
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None,
                         roles=("recruiter",))
    py = db.execute(select(Course).where(Course.tenant_id == tid,
                                         Course.slug == "python")).scalar_one()
    draft = None
    ok = False
    try:
        before = public_courses(request=_Req(), db=db)
        assert not any(c["slug"] == "python" for c in before)
        print("1. seeded course 'python' initially INVISIBLE publicly (all 8 unpublished) ✅")

        publish_course(course_id=py.id, body=PublishIn(is_published=True), ctx=ctx, db=db)
        after = public_courses(request=_Req(), db=db)
        row = next((c for c in after if c["slug"] == "python"), None)
        assert row is not None
        allowed = {"title", "slug", "description", "syllabus", "level", "duration_weeks",
                   "fee", "currency", "next_cohort_start"}
        assert set(row.keys()) == allowed, f"unexpected public fields: {set(row.keys()) - allowed}"
        assert not any(k in row for k in ("id", "tenant_id", "is_published", "status"))
        print(f"2. published → visible publicly with SAFE FIELDS ONLY ({sorted(row.keys())}) ✅")

        draft = create_course(body=CourseIn(title=f"Probe Draft {TAG}", slug="a2-probe-draft"),
                              ctx=ctx, db=db, idempotency_key=None)
        assert not any(c["slug"] == "a2-probe-draft"
                       for c in public_courses(request=_Req(), db=db))
        print("3. a fresh UNPUBLISHED course does NOT leak on the public surface ✅")

        publish_course(course_id=py.id, body=PublishIn(is_published=False), ctx=ctx, db=db)
        assert not any(c["slug"] == "python" for c in public_courses(request=_Req(), db=db))
        print("4. unpublish → gone from the public surface ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(update(Course).where(Course.tenant_id == tid, Course.slug == "python")
                   .values(is_published=False, status="draft"))
        db.execute(Course.__table__.delete().where(Course.tenant_id == tid,
                                                    Course.slug == "a2-probe-draft"))
        db.commit(); db.close()
        print("5. probe cleaned (python re-unpublished, draft removed)")
    print("A2 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
