"""Academy vertical router (A1 shell + A2 catalog).

Every STAFF route depends on `require_feature("academy")` (404 when
FEATURE_ACADEMY off, probe-proof) AND `_require_staff` (candidate/client 403).
The PUBLIC routes are unauthenticated (marketing-facing) but STILL gated by the
academy flag via `is_enabled` (no ctx needed) so the whole vertical is
probe-proof; they resolve the tenant from the Host and return PUBLISHED-ONLY
courses through an explicit safe-field allowlist — no draft, no internal field,
no PII (courses carry none).

Importing app.models_academy registers the academy tables on Base.metadata.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models_academy  # noqa: F401 — registers academy tables on Base.metadata
from ..audit import write_audit
from ..config import settings
from ..context import RequestContext, tenant_from_host
from ..db import get_db
from ..deps import get_current_context
from ..features import is_enabled, require_feature
from ..idempotency import get_cached, store
from ..models import Notification, Tenant
from ..models_academy import Cohort, Course, Enrollment
from .staffing import _require_staff, _tid

router = APIRouter()
BU = "ACADEMY"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _err(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


# ── A1 gate proof ────────────────────────────────────────────────
@router.get("/ping")
def ping(ctx: RequestContext = Depends(require_feature("academy"))):
    """A1 gate proof: 404 when FEATURE_ACADEMY is off; 200 when on."""
    return {"vertical": "academy", "status": "ok"}


# ── serializers ──────────────────────────────────────────────────
def _course_dict(c: Course) -> dict:
    """STAFF view — full record (internal fields included)."""
    return {"id": str(c.id), "title": c.title, "slug": c.slug, "description": c.description,
            "syllabus": c.syllabus, "level": c.level, "duration_weeks": c.duration_weeks,
            "fee": float(c.fee) if c.fee is not None else None, "currency": c.currency,
            "is_published": c.is_published, "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None}


def _public_course_dict(c: Course, next_start: dt.date | None) -> dict:
    """PUBLIC view — an explicit ALLOWLIST of safe display fields. NEVER include
    id/tenant_id/status/is_published/timestamps or any internal field. Courses
    carry no PII, so this surface is PII-free by construction."""
    return {"title": c.title, "slug": c.slug, "description": c.description,
            "syllabus": c.syllabus, "level": c.level, "duration_weeks": c.duration_weeks,
            "fee": float(c.fee) if c.fee is not None else None, "currency": c.currency,
            "next_cohort_start": next_start.isoformat() if next_start else None}


# ── STAFF: course CRUD + publish ─────────────────────────────────
class CourseIn(BaseModel):
    title: str
    slug: str | None = None
    description: str | None = None
    syllabus: str | None = None
    level: str | None = None
    duration_weeks: int | None = None
    fee: float | None = None
    currency: str | None = None

    @field_validator("title")
    @classmethod
    def _t(cls, v):
        v = (v or "").strip()
        if not (2 <= len(v) <= 120):
            raise ValueError("Course title must be 2-120 characters")
        return v

    @field_validator("slug")
    @classmethod
    def _s(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric words separated by hyphens")
        return v

    @field_validator("fee")
    @classmethod
    def _f(cls, v):
        if v is not None and v < 0:
            raise ValueError("fee cannot be negative")
        return v


def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "course"


def _course_or_404(db, ctx, course_id):
    c = db.execute(select(Course).where(
        Course.id == course_id, Course.tenant_id == _tid(ctx),
        Course.business_unit_id == BU, Course.deleted_at.is_(None))).scalar_one_or_none()
    if c is None:
        raise _err(404, "NOT_FOUND", "Course not found")
    return c


@router.post("/courses")
def create_course(body: CourseIn, ctx: RequestContext = Depends(require_feature("academy")),
                  db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    slug = body.slug or _slugify(body.title)
    if db.execute(select(Course).where(Course.tenant_id == _tid(ctx), Course.slug == slug,
                                       Course.deleted_at.is_(None))).scalar_one_or_none():
        raise _err(409, "SLUG_TAKEN", f"A course with slug '{slug}' already exists")
    c = Course(tenant_id=_tid(ctx), business_unit_id=BU, title=body.title, slug=slug,
               description=body.description, syllabus=body.syllabus, level=body.level,
               duration_weeks=body.duration_weeks,
               fee=body.fee if body.fee is not None else 50000,
               currency=body.currency or "INR")
    db.add(c)
    db.flush()
    write_audit(db, ctx, "academy.course_create", "course", c.id, after={"slug": slug})
    db.commit()
    res = _course_dict(c)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


class CourseUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    syllabus: str | None = None
    level: str | None = None
    duration_weeks: int | None = None
    fee: float | None = None
    currency: str | None = None

    @field_validator("fee")
    @classmethod
    def _f(cls, v):
        if v is not None and v < 0:
            raise ValueError("fee cannot be negative")
        return v


@router.patch("/courses/{course_id}")
def update_course(course_id: uuid.UUID, body: CourseUpdateIn,
                  ctx: RequestContext = Depends(require_feature("academy")),
                  db: Session = Depends(get_db)):
    _require_staff(ctx)
    c = _course_or_404(db, ctx, course_id)
    for field in ("title", "description", "syllabus", "level", "duration_weeks", "fee", "currency"):
        v = getattr(body, field)
        if v is not None:
            setattr(c, field, v)
    write_audit(db, ctx, "academy.course_update", "course", c.id, after={"slug": c.slug})
    db.commit()
    return _course_dict(c)


@router.get("/courses")
def list_courses(ctx: RequestContext = Depends(require_feature("academy")),
                 db: Session = Depends(get_db)):
    """Staff catalog — ALL courses incl. unpublished/draft."""
    _require_staff(ctx)
    rows = db.execute(select(Course).where(
        Course.tenant_id == _tid(ctx), Course.business_unit_id == BU,
        Course.deleted_at.is_(None)).order_by(Course.title.asc())).scalars().all()
    return [_course_dict(c) for c in rows]


@router.get("/courses/{course_id}")
def get_course(course_id: uuid.UUID, ctx: RequestContext = Depends(require_feature("academy")),
               db: Session = Depends(get_db)):
    _require_staff(ctx)
    return _course_dict(_course_or_404(db, ctx, course_id))


class PublishIn(BaseModel):
    is_published: bool


@router.post("/courses/{course_id}/publish")
def publish_course(course_id: uuid.UUID, body: PublishIn,
                   ctx: RequestContext = Depends(require_feature("academy")),
                   db: Session = Depends(get_db)):
    """The control that flips a course between draft and public. Publishing sets
    is_published=true + status='active' (both parts of the public browse
    condition); unpublishing reverts to draft — the course vanishes from the
    public surface immediately."""
    _require_staff(ctx)
    c = _course_or_404(db, ctx, course_id)
    c.is_published = body.is_published
    c.status = "active" if body.is_published else "draft"
    write_audit(db, ctx, "academy.course_publish", "course", c.id,
                after={"is_published": c.is_published, "status": c.status})
    db.commit()
    return _course_dict(c)


# ── STAFF: minimal cohorts ───────────────────────────────────────
class CohortIn(BaseModel):
    name: str
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    trainer_id: uuid.UUID | None = None
    capacity: int | None = None
    mode: str = "online"
    status: str = "planned"

    @field_validator("mode")
    @classmethod
    def _m(cls, v):
        if v not in ("online", "offline", "hybrid"):
            raise ValueError("mode must be online, offline or hybrid")
        return v

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v not in ("planned", "open", "running", "completed", "cancelled"):
            raise ValueError("invalid cohort status")
        return v


@router.post("/courses/{course_id}/cohorts")
def create_cohort(course_id: uuid.UUID, body: CohortIn,
                  ctx: RequestContext = Depends(require_feature("academy")),
                  db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    course = _course_or_404(db, ctx, course_id)
    if body.end_date and body.start_date and body.end_date < body.start_date:
        raise _err(422, "VALIDATION_ERROR", "end_date cannot precede start_date")
    ch = Cohort(tenant_id=_tid(ctx), business_unit_id=BU, course_id=course.id, name=body.name,
                start_date=body.start_date, end_date=body.end_date, trainer_id=body.trainer_id,
                capacity=body.capacity, mode=body.mode, status=body.status)
    db.add(ch)
    db.flush()
    write_audit(db, ctx, "academy.cohort_create", "cohort", ch.id, after={"course_id": str(course.id)})
    db.commit()
    res = {"id": str(ch.id), "course_id": str(course.id), "name": ch.name,
           "start_date": ch.start_date.isoformat() if ch.start_date else None,
           "end_date": ch.end_date.isoformat() if ch.end_date else None,
           "trainer_id": str(ch.trainer_id) if ch.trainer_id else None,
           "capacity": ch.capacity, "mode": ch.mode, "status": ch.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/courses/{course_id}/cohorts")
def list_cohorts(course_id: uuid.UUID, ctx: RequestContext = Depends(require_feature("academy")),
                 db: Session = Depends(get_db)):
    _require_staff(ctx)
    course = _course_or_404(db, ctx, course_id)
    rows = db.execute(select(Cohort).where(
        Cohort.course_id == course.id, Cohort.tenant_id == _tid(ctx),
        Cohort.deleted_at.is_(None)).order_by(Cohort.start_date.asc().nullslast())).scalars().all()
    return [{"id": str(ch.id), "name": ch.name,
             "start_date": ch.start_date.isoformat() if ch.start_date else None,
             "end_date": ch.end_date.isoformat() if ch.end_date else None,
             "trainer_id": str(ch.trainer_id) if ch.trainer_id else None,
             "capacity": ch.capacity, "mode": ch.mode, "status": ch.status} for ch in rows]


# ── PUBLIC (unauthenticated, marketing-facing) ───────────────────
def _public_tenant(request: Request, db: Session) -> Tenant:
    """Resolve the tenant from the Host (no session), 404 on unknown — mirrors the
    public registration surface. Also enforces the academy flag (probe-proof) via
    is_enabled (no ctx needed for the env-global resolver)."""
    if not is_enabled("academy"):
        raise _err(404, "NOT_FOUND", "Not found")
    slug = tenant_from_host(request.headers.get("host", ""), settings.app_base_domain)
    tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if tenant is None:
        raise _err(404, "NOT_FOUND", "Not found")
    return tenant


def _next_cohort_start(db, tenant_id, course_id) -> dt.date | None:
    today = dt.datetime.now(dt.timezone.utc).date()
    return db.execute(select(func.min(Cohort.start_date)).where(
        Cohort.tenant_id == tenant_id, Cohort.course_id == course_id,
        Cohort.deleted_at.is_(None), Cohort.status.in_(("planned", "open", "running")),
        Cohort.start_date >= today)).scalar_one()


@router.get("/public/courses")
def public_courses(request: Request, db: Session = Depends(get_db)):
    """PUBLISHED-ONLY, safe-fields-only, tenant-by-Host. The marketing Training
    page's data source. Guarantees: (a) is_published=true AND status='active'
    filter → no draft leaks; (b) _public_course_dict is an explicit allowlist →
    no internal field; (c) tenant resolved from Host → cross-tenant isolation."""
    tenant = _public_tenant(request, db)
    rows = db.execute(select(Course).where(
        Course.tenant_id == tenant.id, Course.business_unit_id == BU,
        Course.is_published.is_(True), Course.status == "active",
        Course.deleted_at.is_(None)).order_by(Course.title.asc())).scalars().all()
    return [_public_course_dict(c, _next_cohort_start(db, tenant.id, c.id)) for c in rows]


@router.get("/public/courses/{slug}")
def public_course_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    tenant = _public_tenant(request, db)
    c = db.execute(select(Course).where(
        Course.tenant_id == tenant.id, Course.business_unit_id == BU, Course.slug == slug,
        Course.is_published.is_(True), Course.status == "active",
        Course.deleted_at.is_(None))).scalar_one_or_none()
    if c is None:
        raise _err(404, "NOT_FOUND", "Course not found")
    return _public_course_dict(c, _next_cohort_start(db, tenant.id, c.id))




# ═══════════════════════════════════════════════════════════════════
# A3 — SEPARATE academy-student auth + public registration + ID card
# ═══════════════════════════════════════════════════════════════════
import datetime as _dt  # noqa: E402

from fastapi import Response  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from pydantic import BaseModel as _BM  # noqa: E402  (grouped A3 block)

from ..academy_deps import ACADEMY_COOKIE, StudentContext, get_current_student  # noqa: E402
from ..captcha import verify_captcha  # noqa: E402
from ..crypto import blind_index  # noqa: E402
from ..models import Consent  # noqa: E402
from ..models_academy import Student  # noqa: E402
from ..notify import enqueue  # noqa: E402
from ..routers.privacy import POLICY_VERSION  # noqa: E402
from ..security import create_academy_token, hash_password, verify_password  # noqa: E402
from .. import storage  # noqa: E402
from ..validation import normalize_phone, validate_email, validate_name, validate_password  # noqa: E402

_ID_CARD_TYPES = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
_ID_CARD_MAX_BYTES = 5 * 1024 * 1024   # 5 MB

# [FOUNDER DRAFT — legal review pending]. STOP-3: not final legal prose. Minors'
# verifiable-parental-consent flow is a launch-blocker needing legal (children's DPDP).
_ACADEMY_CONSENT_NOTICE = (
    "[FOUNDER DRAFT — legal review pending] I consent to SPS Technosoft Academy "
    "processing the personal data and college ID I provide for enrolment, the "
    "entrance aptitude test, and course administration. Under-18 applicants require "
    "a parent/guardian to consent on their behalf.")


def _now():
    return _dt.datetime.now(_dt.timezone.utc)


# ── the SEPARATE academy-student auth system ─────────────────────
class AcademyLoginIn(_BM):
    email: str
    password: str


@router.post("/auth/login")
def academy_login(body: AcademyLoginIn, request: Request, response: Response,
                  db: Session = Depends(get_db)):
    """Authenticate an academy STUDENT against academy.students (argon2) and issue
    the academy token in a DISTINCT cookie, signed with a DISTINCT secret. Never
    touches shared.users → a staff/candidate/client credential cannot log in here."""
    if not is_enabled("academy"):
        raise _err(404, "NOT_FOUND", "Not found")
    tenant = _public_tenant(request, db)   # tenant-from-Host + flag gate
    st = db.execute(select(Student).where(
        Student.tenant_id == tenant.id, Student.email == body.email,
        Student.deleted_at.is_(None))).scalar_one_or_none()
    if st is None or not st.password_hash or not verify_password(st.password_hash, body.password):
        raise _err(401, "INVALID_CREDENTIALS", "Invalid email or password")
    token = create_academy_token({"sub": str(st.id), "tenant_id": str(tenant.id),
                                  "kind": "academy_student", "role": "student",
                                  "email": st.email, "student_id": st.student_id})
    response.set_cookie(key=ACADEMY_COOKIE, value=token, max_age=settings.access_ttl_seconds,
                        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return {"student_id": str(st.id), "email": st.email, "full_name": st.full_name,
            "home": "/academy/student"}


@router.get("/auth/me")
def academy_me(student: StudentContext = Depends(get_current_student),
               db: Session = Depends(get_db)):
    """The academy-student identity. Rejects a staffing token (wrong cookie/secret/kind)."""
    st = db.get(Student, student.student_id)
    return {"student_id": str(st.id), "email": st.email, "full_name": st.full_name,
            "college_student_id": st.student_id, "college_name": st.college_name,
            "course_degree": st.course_degree, "kind": "academy_student"}


@router.post("/auth/logout")
def academy_logout(response: Response):
    response.delete_cookie(key=ACADEMY_COOKIE, path="/")
    return {"ok": True}


# ── public registration config + ID-card presign ────────────────
@router.get("/register/config")
def register_config():
    if not is_enabled("academy"):
        raise _err(404, "NOT_FOUND", "Not found")
    return {"hcaptcha_sitekey": settings.hcaptcha_sitekey, "policy_version": POLICY_VERSION,
            "consent_notice": _ACADEMY_CONSENT_NOTICE, "id_card_content_types": sorted(_ID_CARD_TYPES)}


class IdCardPresignIn(_BM):
    content_type: str


@router.post("/register/id-card/presign")
def id_card_presign(body: IdCardPresignIn, request: Request, db: Session = Depends(get_db)):
    """Public: presign an ID-card PUT (B.1 resume pattern). Client uploads to the
    key, then submits it to /register/student which CONFIRMS via head_object."""
    tenant = _public_tenant(request, db)
    ext = _ID_CARD_TYPES.get(body.content_type)
    if ext is None:
        raise _err(422, "UNSUPPORTED_TYPE", "ID card must be JPEG, PNG or PDF")
    key = f"tenant={tenant.id}/business_unit=ACADEMY/students/idcard/{uuid.uuid4()}.{ext}"
    return {"upload_url": storage.presign_put(key, body.content_type), "key": key,
            "expires_in": storage.PRESIGN_PUT_TTL}


# ── public student registration (academy.students credential, NO shared.users) ──
class StudentRegisterIn(_BM):
    full_name: str
    email: str
    phone: str
    password: str
    student_id: str
    college_name: str
    course_degree: str
    year_of_study: str
    date_of_birth: _dt.date
    id_card_key: str
    consent_data_processing: bool
    guardian_name: str | None = None
    guardian_consent: bool | None = None

    @field_validator("full_name")
    @classmethod
    def _n(cls, v): return validate_name(v)

    @field_validator("email")
    @classmethod
    def _e(cls, v): return validate_email(v)

    @field_validator("password")
    @classmethod
    def _p(cls, v): return validate_password(v)

    @field_validator("student_id", "college_name", "course_degree", "year_of_study")
    @classmethod
    def _req(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("This field is required")
        return v


def _age_on(dob: _dt.date, today: _dt.date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


@router.post("/register/student")
def register_student(body: StudentRegisterIn, request: Request, db: Session = Depends(get_db),
                     captcha_token: str | None = Header(default=None),
                     idempotency_key: str | None = Header(default=None)):
    """PUBLIC academy student registration (one all-or-nothing txn), students-only:
    captcha → age/guardian → consent → tenant → academy dedup → academy.students row
    (argon2 password_hash + encrypted phone + identity + confirmed id_card + consent
    on-row) + audit → 2 B.10 emails. NO shared.users write. students.user_id stays
    null (bridge-only, not auth)."""
    if not is_enabled("academy"):
        raise _err(404, "NOT_FOUND", "Not found")
    if not verify_captcha(captcha_token):
        raise _err(400, "CAPTCHA_FAILED", "Captcha verification failed — please retry")
    if not body.consent_data_processing:
        raise _err(422, "CONSENT_REQUIRED", "Consent to data processing is required")

    today = _now().date()
    age = _age_on(body.date_of_birth, today)
    is_minor = age < 18
    if is_minor and not (body.guardian_name and body.guardian_name.strip()
                         and body.guardian_consent is True):
        raise _err(422, "GUARDIAN_CONSENT_REQUIRED",
                   "Applicants under 18 require a guardian name and guardian consent")

    tenant = _public_tenant(request, db)
    if (cached := get_cached(str(tenant.id), idempotency_key)):
        return cached

    # academy dedup: an existing academy student with this email OR student_id → 409
    if db.execute(select(Student).where(
            Student.tenant_id == tenant.id, Student.deleted_at.is_(None),
            (Student.email == body.email) | (Student.student_id == body.student_id))).first():
        raise _err(409, "STUDENT_EXISTS", "A student with this email or student ID already exists")

    # confirm the pre-uploaded ID card (server-side size/type re-check; B.1 pattern)
    if not body.id_card_key.startswith(f"tenant={tenant.id}/business_unit=ACADEMY/students/idcard/"):
        raise _err(422, "BAD_ID_CARD_KEY", "Invalid ID card reference")
    meta = storage.head_object(body.id_card_key)
    if meta is None:
        raise _err(422, "ID_CARD_MISSING", "Upload your college ID card before submitting")
    if meta.get("ContentLength", 0) > _ID_CARD_MAX_BYTES:
        raise _err(422, "ID_CARD_TOO_LARGE", "ID card exceeds the 5 MB limit")

    phone = normalize_phone(body.phone)
    student = Student(
        tenant_id=tenant.id, business_unit_id=BU, full_name=body.full_name, email=body.email,
        password_hash=hash_password(body.password),      # academy credential (argon2)
        phone_enc=phone, phone_bidx=blind_index(phone), user_id=None,  # user_id = bridge-only
        source="self_registration", student_id=body.student_id, college_name=body.college_name,
        course_degree=body.course_degree, year_of_study=body.year_of_study,
        date_of_birth=body.date_of_birth, id_card_s3_key=body.id_card_key,
        guardian_name=body.guardian_name.strip() if (is_minor and body.guardian_name) else None,
        guardian_consent=body.guardian_consent if is_minor else None)
    db.add(student)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _err(409, "STUDENT_EXISTS", "A student with this email or student ID already exists")

    # Option A: DPDP consent in the canonical shared.consents ledger (subject_student_id
    # soft-ref). Guardian consent is recorded on the student row + the audit trail.
    db.add(Consent(tenant_id=tenant.id, subject_student_id=student.id, purpose="data_processing",
                   granted=True, policy_version=POLICY_VERSION))
    ctx = RequestContext(tenant_id=str(tenant.id), business_unit_id=BU, user_id=None, roles=("student",))
    if is_minor:
        write_audit(db, ctx, "academy.guardian_consent", "student", student.id,
                    after={"guardian_name": student.guardian_name, "age": age})
    write_audit(db, ctx, "academy.student_register", "student", student.id,
                after={"minor": is_minor, "policy_version": POLICY_VERSION})

    enqueue(db, template_code="student_welcome", recipient=body.email,
            vars={"full_name": body.full_name, "course": body.course_degree},
            tenant_id=tenant.id, business_unit_id=BU,
            idempotency_key=f"academy:welcome:{student.id}")
    enqueue(db, template_code="admin_new_student_application", recipient=settings.academy_admin_email,
            vars={"full_name": body.full_name, "email": body.email, "course": body.course_degree,
                  "college": body.college_name},
            tenant_id=tenant.id, business_unit_id=BU,
            idempotency_key=f"academy:admin:{student.id}")
    db.commit()

    res = {"id": str(student.id), "status": "registered", "minor": is_minor,
           "policy_version": POLICY_VERSION}
    store(str(tenant.id), idempotency_key, res)
    return res


# ═══════════════════════════════════════════════════════════════════
# A4 — admin-triggered entrance aptitude issue (60Q academy)
# ═══════════════════════════════════════════════════════════════════
import datetime as _dt2  # noqa: E402

from ..models_academy import Enrollment  # noqa: E402
from ..models_staffing import Test  # noqa: E402
from .. import assessment_engine as _engine  # noqa: E402
from .assessments import select_bank_paper  # noqa: E402  (shared engine seam)


def _require_academy_pairing(enr) -> None:
    """BU↔pairing INVARIANT (carry-forward from the 0035 CHECK, enforced at the
    WRITER not a BU-coupled DB CHECK): an ACADEMY test must carry the academy
    pairing (enrollment + student), never the staffing one. A RAISED domain error
    (canonical envelope) — NOT a bare assert, which would 500 and be stripped under
    python -O. Also guards a null student_id (folds the 0035->A4 carry-forward:
    an academy pairing with a null student_id would otherwise hit ck_tests_one_identity
    with a raw IntegrityError)."""
    if BU != "ACADEMY" or enr.student_id is None:
        raise _err(409, "BU_PAIRING_INVARIANT",
                   "Academy aptitude tests require an academy enrollment with a student")


@router.post("/enrollments/{enrollment_id}/aptitude/issue")
def issue_aptitude(enrollment_id: uuid.UUID,
                   ctx: RequestContext = Depends(require_feature("academy")),
                   db: Session = Depends(get_db),
                   idempotency_key: str | None = Header(default=None)):
    """ADMIN-triggered (decision 8): freeze a 60Q academy aptitude paper for an
    enrollment at status='applied' + mint the one-time take link. Writes the
    ACADEMY identity pairing on the test row (enrollment_id + student_id set,
    staffing refs null). Student/candidate role → 403 (cannot self-issue)."""
    _require_staff(ctx)
    if (cached := get_cached(str(ctx.tenant_id), idempotency_key)):
        return cached
    enr = db.execute(select(Enrollment).where(
        Enrollment.id == enrollment_id, Enrollment.tenant_id == _tid(ctx),
        Enrollment.business_unit_id == BU, Enrollment.deleted_at.is_(None))).scalar_one_or_none()
    if enr is None:
        raise _err(404, "NOT_FOUND", "Enrollment not found")
    if enr.status != "applied":
        raise _err(409, "STATUS_INVALID", "Enrollment must be at 'applied' to issue an aptitude test")

    now = _dt2.datetime.now(_dt2.timezone.utc)
    prior = db.execute(select(Test).where(Test.enrollment_id == enr.id, Test.deleted_at.is_(None))
                       .order_by(Test.attempt_no.desc())).scalars().all()
    for t in prior:
        if t.status in ("issued", "started") and t.valid_until > now:
            raise _err(409, "TEST_ACTIVE", "An active aptitude link already exists for this enrollment")
    last_sub = next((t for t in prior if t.status == "submitted"), None)
    if last_sub is not None and last_sub.passed is False:
        cooldown = last_sub.submitted_at + _dt2.timedelta(days=settings.test_retake_cooldown_days)
        if now < cooldown:
            raise _err(409, "RETAKE_COOLDOWN", f"Retake allowed after {cooldown.date().isoformat()}")

    frozen = select_bank_paper(db, _tid(ctx), BU, settings.academy_test_question_count)
    raw_token, token_hash = _engine.new_link_token()

    _require_academy_pairing(enr)
    test = Test(tenant_id=_tid(ctx), business_unit_id=BU,
                application_id=None, candidate_id=None,          # staffing pairing NULL
                enrollment_id=enr.id, student_id=enr.student_id,  # academy pairing SET
                link_token_hash=token_hash,
                valid_until=now + _dt2.timedelta(hours=settings.test_link_ttl_hours),
                attempt_no=(max((t.attempt_no for t in prior), default=0) + 1),
                served_questions=frozen)
    db.add(test)
    db.flush()
    write_audit(db, ctx, "academy.aptitude_issue", "test", test.id,
                after={"enrollment_id": str(enr.id), "attempt_no": test.attempt_no,
                       "question_count": len(frozen)})
    # aptitude-invite notification — carries the /take/{token} link to the STUDENT.
    # The raw token exists ONLY here (new_link_token shows it once); capture it now.
    # Idempotent on the issued test: re-issue/retake = new test = new token = new
    # invite; the same issue can't double-send (unique idempotency_key).
    _student = db.get(Student, enr.student_id)
    _course = db.get(Course, enr.course_id)
    if _student is not None and _student.email:
        enqueue(db, template_code="academy_aptitude_invite", recipient=_student.email,
                vars={"full_name": _student.full_name,
                      "course": _course.title if _course else "your course",
                      "take_link": f"/take/{raw_token}",
                      "valid_until": test.valid_until.date().isoformat()},
                tenant_id=_tid(ctx), business_unit_id=BU,
                idempotency_key=f"academy:aptitude_invite:{test.id}")
    db.commit()
    res = {"test_id": str(test.id), "take_path": f"/api/take/{raw_token}",
           "valid_until": test.valid_until.isoformat(), "attempt_no": test.attempt_no,
           "question_count": len(frozen),
           "time_limit_minutes": settings.academy_test_time_limit_minutes}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


# ═══════════════════════════════════════════════════════════════════
# A6 — payment activation (STUB; Part-D swaps in Razorpay order+webhook)
# ═══════════════════════════════════════════════════════════════════
from ..models_academy import Payment, Student  # noqa: E402
from .. import academy_receipt_pdf  # noqa: E402


def _create_or_get_payment(db, enr, ctx) -> Payment:
    """Lazy, idempotent payment-intent seam (Part-D: also creates the Razorpay
    ORDER here). ONE open (non-paid) row per enrollment: an existing open row is
    returned; a create against an already-active/paid enrollment is refused with a
    clean 4xx (never mint a second payable row against a paid enrolment)."""
    if enr.status in ("active", "completed") or enr.payment_status == "paid":
        raise _err(409, "ENROLLMENT_NOT_PAYABLE",
                   "Enrollment is already active/paid — no new payment can be created")
    existing = db.execute(select(Payment).where(
        Payment.enrollment_id == enr.id, Payment.status == "created",
        Payment.deleted_at.is_(None)).order_by(Payment.created_at.desc())).scalars().first()
    if existing is not None:
        return existing
    # amount is READ off the enrollment's stamped final_fee — never recomputed (C.2)
    pay = Payment(tenant_id=_tid(ctx), business_unit_id=BU, enrollment_id=enr.id,
                  amount=enr.final_fee, currency="INR", status="created", provider="stub")
    db.add(pay); db.flush()
    return pay


def _activate_payment(db, pay: Payment, enr, ctx, provider_ref: str) -> None:
    """The SINGLE activation seam the stub confirm AND the future HMAC-verified
    Razorpay webhook both enter. Part-D adds signature-verify + order-lookup BEFORE
    this call and changes NOTHING after it. Marks paid, activates the enrolment,
    renders+stores the receipt PDF, enqueues the confirmation email."""
    now = dt.datetime.now(dt.timezone.utc)
    pay.status = "paid"
    pay.paid_at = now
    pay.provider_ref = provider_ref
    enr.payment_status = "paid"
    enr.payment_id = pay.id
    enr.status = "active"                                   # offered→active
    # receipt PDF via the existing ReportLab+S3 seam
    course = db.get(Course, enr.course_id)
    student = db.get(Student, enr.student_id)
    pdf = academy_receipt_pdf.build_receipt_pdf(
        payment=pay, enrollment=enr, course_title=course.title if course else "—",
        student_name=student.full_name if student else "—")
    key = (f"tenant={enr.tenant_id}/business_unit=ACADEMY/enrollments/{enr.id}/"
           f"receipts/{pay.id}.pdf")
    storage._client().put_object(Bucket=storage.settings.storage_bucket, Key=key,
                                 Body=pdf, ContentType="application/pdf")
    pay.receipt_s3_key = key
    write_audit(db, ctx, "academy.payment_activate", "payment", pay.id,
                after={"enrollment_id": str(enr.id), "amount": float(pay.amount),
                       "provider_ref": provider_ref, "receipt_s3_key": key})
    # confirmation email — idempotent on the PAYMENT ROW (never the enrollment)
    if student is not None and student.email:
        enqueue(db, template_code="academy_enrolment_active", recipient=student.email,
                vars={"full_name": student.full_name, "course": course.title if course else "—",
                      "amount": float(pay.amount), "currency": pay.currency},
                tenant_id=enr.tenant_id, business_unit_id=BU,
                idempotency_key=f"academy:payment_confirmed:{pay.id}")


def _payment_result(pay: Payment, enr) -> dict:
    return {"payment_id": str(pay.id), "status": pay.status,
            "amount": float(pay.amount), "currency": pay.currency,
            "paid_at": pay.paid_at.isoformat() if pay.paid_at else None,
            "enrollment_status": enr.status,
            "receipt_url": storage.presign_get(pay.receipt_s3_key) if pay.receipt_s3_key else None}


@router.post("/enrollments/{enrollment_id}/pay")
def confirm_payment(enrollment_id: uuid.UUID,
                    ctx: RequestContext = Depends(require_feature("academy")),
                    db: Session = Depends(get_db)):
    """STUB confirm — simulates the Razorpay webhook callback (Part-D replaces the
    staff gate with HMAC signature verification + order lookup, then calls the SAME
    _activate_payment). Idempotency is keyed on the PAYMENT ROW's own status:
      1. this payment already paid → no-op success (webhook REDELIVERY of THIS payment).
      2. else the enrolment MUST be at 'offered' to activate:
         - offered → activate.
         - NOT offered (tested, or already active via a DIFFERENT payment) → 4xx
           conflict (a distinct unpaid payment vs an active enrolment is a real
           two-payments conflict, never swallowed as success)."""
    _require_staff(ctx)
    enr = db.execute(select(Enrollment).where(
        Enrollment.id == enrollment_id, Enrollment.tenant_id == _tid(ctx),
        Enrollment.business_unit_id == BU, Enrollment.deleted_at.is_(None))).scalar_one_or_none()
    if enr is None:
        raise _err(404, "NOT_FOUND", "Enrollment not found")
    current = db.execute(select(Payment).where(
        Payment.enrollment_id == enr.id, Payment.deleted_at.is_(None))
        .order_by(Payment.created_at.desc())).scalars().first()
    # 1. redelivery of THIS payment (keyed on the payment row's status, not the enrolment)
    if current is not None and current.status == "paid":
        return _payment_result(current, enr)               # no-op success
    # 2. this payment not paid → the enrolment must be offered to activate
    if enr.status != "offered":
        raise _err(409, "STATUS_INVALID",
                   "Enrollment must be at 'offered' to activate payment")
    pay = _create_or_get_payment(db, enr, ctx)
    _activate_payment(db, pay, enr, ctx, provider_ref=f"stub-{uuid.uuid4()}")
    db.commit()
    return _payment_result(pay, enr)


# ═══════════════════════════════════════════════════════════════════
# A4/FE#4 — student-facing enrolments read (the student's OWN data only)
# ═══════════════════════════════════════════════════════════════════
@router.get("/students/me/enrollments")
def my_enrollments(student: StudentContext = Depends(get_current_student),
                   db: Session = Depends(get_db)):
    """The AUTHENTICATED student's OWN enrolments. STRICT SCOPING: the student is
    derived from the SESSION only (StudentContext.student_id) — there is NO
    student_id/enrollment_id path or query param, so student A has no request shape
    by which to read student B's rows. NO ANSWER LEAK: `active_test` carries only a
    test's presence + validity (never served questions, correct answers, or the
    one-time token — which is unstored by design anyway)."""
    now = dt.datetime.now(dt.timezone.utc)
    rows = db.execute(select(Enrollment).where(
        Enrollment.student_id == student.student_id,      # session-derived subject ONLY
        Enrollment.business_unit_id == BU,
        Enrollment.deleted_at.is_(None))
        .order_by(Enrollment.created_at.desc())).scalars().all()
    out = []
    for e in rows:
        course = db.get(Course, e.course_id)
        # active test = issued/started, not yet submitted, not expired
        t = db.execute(select(Test).where(
            Test.enrollment_id == e.id, Test.business_unit_id == BU,
            Test.status.in_(("issued", "started")), Test.submitted_at.is_(None),
            Test.valid_until > now, Test.deleted_at.is_(None))
            .order_by(Test.attempt_no.desc())).scalars().first()
        active_test = ({"valid_until": t.valid_until.isoformat(), "attempt_no": t.attempt_no}
                       if t is not None else None)
        out.append({
            "enrollment_id": str(e.id),
            "course": {"title": course.title if course else None,
                       "slug": course.slug if course else None},
            "status": e.status,
            "aptitude_score": float(e.aptitude_score) if e.aptitude_score is not None else None,
            "discount_percent": int(e.discount_percent) if e.discount_percent is not None else None,
            "final_fee": float(e.final_fee) if e.final_fee is not None else None,
            "currency": course.currency if course else "INR",
            "payment_status": e.payment_status,
            "active_test": active_test,
        })
    return out


@router.get("/students/me/notifications")
def my_notifications(student: StudentContext = Depends(get_current_student),
                     db: Session = Depends(get_db)):
    """The AUTHENTICATED student's OWN academy notifications. STRICT SCOPING: keyed
    on the SESSION email (recipient) + BU=ACADEMY — no param, so student A (email A)
    cannot read B's rows. This matters more than the enrolments read: an aptitude
    invite's `vars.take_link` is a LIVE one-time test token, so a cross-student leak
    would hand over a working test link. Academy student email is unique per tenant,
    and the BU filter excludes any staff notification that happens to share an email
    (A3 email-reuse-across-boundary)."""
    if not student.email:
        return []
    rows = db.execute(select(Notification).where(
        Notification.recipient == student.email,
        Notification.tenant_id == uuid.UUID(student.tenant_id),
        Notification.business_unit_id == BU)
        .order_by(Notification.created_at.desc()).limit(50)).scalars().all()
    return [{"id": str(n.id), "template_code": n.template_code,
             "subject": n.rendered_subject, "body": n.rendered_body,
             "take_link": (n.vars or {}).get("take_link"),
             "status": n.status,
             "created_at": n.created_at.isoformat() if n.created_at else None} for n in rows]
