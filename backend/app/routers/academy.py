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
from ..models import Tenant
from ..models_academy import Cohort, Course
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
