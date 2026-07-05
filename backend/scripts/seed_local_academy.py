"""LOCAL-ONLY idempotent walkable-academy seed (frontend bring-up).

Runs INSIDE the backend container against local Postgres. Gives the founder a
browser-walkable dataset: a loginable staff/admin, a loginable student, one
PUBLISHED course (real per-course fee), and enrollments at every status
(applied → tested → offered → active) so every dashboard state renders.

[SAMPLE] content only — no invented business data. NOT a migration, NOT for dev/
prod (the '!' guard refuses anything but the local DB host). Re-runnable.

Logins it provisions (dev-only passwords):
  staff/admin : sandeep@spstechnosoft.com  /  SpsLocal!2026
  student     : student@local.test          /  Student!2026   (the 'offered' one,
                so you can walk offered → pay → active in the UI)
"""
from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import select, text

from app.config import settings
from app.db import get_sessionmaker
from app.models import Tenant, User
from app.models_academy import Cohort, Course, Enrollment, Payment, Student
from app.security import hash_password

STAFF_EMAIL = "sandeep@spstechnosoft.com"
STAFF_PW = "SpsLocal!2026"
STUDENT_PW = "Student!2026"
# A DISTINCT [SAMPLE] course — NOT one of the 8 canonical migration-seeded courses
# (those must stay pristine/draft for the foundation reproducibility test).
COURSE_SLUG = "sample-walkthrough"
COURSE_TITLE = "[SAMPLE] Full-Stack Development"
COURSE_FEE = 55000            # [SAMPLE] real per-course fee (≠ the 50000 default)
COHORT_NAME = "[SAMPLE] Batch 2026-Q3"

# (email, full_name, status, aptitude, discount, is_login_student)
STUDENTS = [
    ("student-applied@local.test", "[SAMPLE] Aarti Applied", "applied", None, None, False),
    ("student-tested@local.test",  "[SAMPLE] Tarun Tested",  "tested",  80.0, 10, False),
    ("student@local.test",         "[SAMPLE] Ofelia Offered", "offered", 88.0, 15, True),
    ("student-active@local.test",  "[SAMPLE] Akhil Active",   "active",  96.0, 20, False),
    ("student-fullprice@local.test", "[SAMPLE] Farah Fullprice", "offered", 60.0, 0, False),  # <75 → full price
]


def main() -> int:
    db = get_sessionmaker()()
    host = os.getenv("DB_HOST", "")
    if host not in ("postgres", "localhost", "127.0.0.1", ""):
        print(f"REFUSING: DB_HOST={host!r} is not local. This seed is local-only.")
        return 1
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()

    # 0) ensure the LOCAL S3 (MinIO) bucket exists — create-if-missing so the
    #    presign→PUT→head_object flow (id-card upload, receipts) works locally.
    #    No-op against real S3 (dev/prod don't run this seed). Same bucket NAME as
    #    dev so keys/paths are identical.
    if settings.s3_endpoint_url:
        from app import storage
        try:
            storage._client().create_bucket(Bucket=settings.storage_bucket)
            print(f"local S3 bucket created: {settings.storage_bucket}")
        except Exception as e:  # noqa: BLE001 — already-exists is the happy path
            msg = type(e).__name__
            print(f"local S3 bucket ready: {settings.storage_bucket} ({msg})")

    # 1) staff/admin login: activate the founder + set a known dev password
    founder = db.execute(select(User).where(User.tenant_id == sps.id,
                                            User.email == STAFF_EMAIL)).scalar_one_or_none()
    if founder is not None:
        founder.password_hash = hash_password(STAFF_PW)
        founder.status = "active"
        print(f"staff login ready: {STAFF_EMAIL} / {STAFF_PW}")
    else:
        print(f"WARN: founder {STAFF_EMAIL} not found (run migrations first)")

    # 2) publish one course with a real per-course fee (mirrors the publish endpoint:
    #    is_published=true + status='active')
    course = db.execute(select(Course).where(
        Course.tenant_id == sps.id, Course.slug == COURSE_SLUG)).scalar_one_or_none()
    if course is None:
        course = Course(tenant_id=sps.id, business_unit_id="ACADEMY",
                        title=COURSE_TITLE, slug=COURSE_SLUG,
                        description="[SAMPLE — YOUR CONTENT] Course description.",
                        fee=COURSE_FEE)
        db.add(course); db.flush()
    course.is_published = True
    course.status = "active"
    course.fee = COURSE_FEE
    print(f"published course: {course.slug} (fee {COURSE_FEE})")

    # 3) one cohort for the roster
    cohort = db.execute(select(Cohort).where(
        Cohort.tenant_id == sps.id, Cohort.course_id == course.id,
        Cohort.name == COHORT_NAME)).scalar_one_or_none()
    if cohort is None:
        cohort = Cohort(tenant_id=sps.id, business_unit_id="ACADEMY", course_id=course.id,
                        name=COHORT_NAME, status="running")
        db.add(cohort); db.flush()

    # 4) students + enrollments spanning every status
    for i, (email, name, status, apt, disc, is_login) in enumerate(STUDENTS):
        stu = db.execute(select(Student).where(
            Student.tenant_id == sps.id, Student.email == email)).scalar_one_or_none()
        if stu is None:
            stu = Student(tenant_id=sps.id, business_unit_id="ACADEMY", full_name=name,
                          email=email, student_id=f"SAMPLE-{1001 + i}",
                          college_name="[SAMPLE] College of Engineering",
                          course_degree="[SAMPLE] B.Tech CSE", year_of_study="[SAMPLE] 3rd")
            db.add(stu); db.flush()
        stu.password_hash = hash_password(STUDENT_PW)

        enr = db.execute(select(Enrollment).where(
            Enrollment.tenant_id == sps.id, Enrollment.cohort_id == cohort.id,
            Enrollment.student_id == stu.id)).scalar_one_or_none()
        final_fee = round(COURSE_FEE * (100 - disc) / 100, 2) if disc is not None else None
        if enr is None:
            enr = Enrollment(tenant_id=sps.id, business_unit_id="ACADEMY", cohort_id=cohort.id,
                             student_id=stu.id, course_id=course.id, status=status)
            db.add(enr); db.flush()
        enr.status = status
        enr.aptitude_score = apt
        enr.discount_percent = disc
        enr.final_fee = final_fee
        enr.payment_status = "paid" if status == "active" else "pending"

        if status == "active":
            pay = db.execute(select(Payment).where(
                Payment.enrollment_id == enr.id)).scalar_one_or_none()
            if pay is None:
                pay = Payment(tenant_id=sps.id, business_unit_id="ACADEMY",
                              enrollment_id=enr.id, amount=final_fee, currency="INR",
                              status="paid", provider="stub", provider_ref="stub-seed",
                              paid_at=db.execute(text("SELECT now()")).scalar_one())
                db.add(pay); db.flush()
            enr.payment_id = pay.id
        who = "  ← STUDENT LOGIN" if is_login else ""
        print(f"enrollment: {name} → {status} (fee={final_fee}){who}")

    db.commit()
    print(f"\nstudent login ready: student@local.test / {STUDENT_PW}")
    print("walkable dataset seeded.")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
