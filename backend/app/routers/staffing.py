"""Staffing vertical endpoints (Part 5): clients, candidates, jobs, applications,
pipeline + the employer overview read-model. All authenticated, tenant-scoped;
two-axis tables also scoped to business_unit_id='STAFFING'. Candidates are
tenant-scoped (talent pool). Writes honor Idempotency-Key and require a staff role.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models_staffing import Application, Candidate, Client, Job
from ..validation import normalize_phone, validate_email, validate_name, validate_pan

router = APIRouter()
BU = "STAFFING"

STAFF_ROLES = {"owner", "super_admin", "admin", "business_manager", "manager",
               "recruiter", "coordinator", "employee", "client"}

# Pipeline state machine (Part 5) — legal transitions; anything else → 409.
TRANSITIONS = {
    "sourced": {"screened", "rejected", "on_hold"},
    "screened": {"assessed", "rejected", "on_hold"},
    "assessed": {"submitted", "rejected", "on_hold"},
    "submitted": {"interview", "rejected", "on_hold"},
    "interview": {"offer", "rejected", "on_hold"},
    "offer": {"placed", "rejected", "on_hold"},
    "placed": set(),
    "rejected": set(),
    "on_hold": {"screened", "assessed", "submitted", "interview", "offer", "rejected"},
}


def _require_staff(ctx: RequestContext):
    if not (set(ctx.roles) & STAFF_ROLES):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Staff role required"})


def _tid(ctx: RequestContext) -> uuid.UUID:
    return uuid.UUID(str(ctx.tenant_id))


# ── schemas ──────────────────────────────────────────────────────
class ClientIn(BaseModel):
    name: str
    industry: str | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, v): return validate_name(v)


class CandidateIn(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    pan: str | None = None
    skills: list[str] | None = None
    total_exp: float | None = None

    @field_validator("full_name")
    @classmethod
    def _fn(cls, v): return validate_name(v)

    @field_validator("email")
    @classmethod
    def _e(cls, v): return validate_email(v) if v else v

    @field_validator("phone")
    @classmethod
    def _p(cls, v): return normalize_phone(v) if v else v

    @field_validator("pan")
    @classmethod
    def _pan(cls, v): return validate_pan(v) if v else v


class JobIn(BaseModel):
    title: str
    client_id: uuid.UUID | None = None
    jd_text: str | None = None
    skills: list[str] | None = None
    min_exp: int | None = None
    max_exp: int | None = None

    @field_validator("title")
    @classmethod
    def _t(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("Title is required")
        return v


class ApplicationIn(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID


class StageIn(BaseModel):
    stage: str


# ── helpers ──────────────────────────────────────────────────────
def _client_dict(c: Client): return {"id": str(c.id), "name": c.name, "industry": c.industry, "status": c.status}
def _job_dict(j: Job): return {"id": str(j.id), "title": j.title, "client_id": str(j.client_id) if j.client_id else None,
                               "status": j.status, "skills": j.skills, "min_exp": j.min_exp, "max_exp": j.max_exp}
def _cand_dict(c: Candidate): return {"id": str(c.id), "full_name": c.full_name, "email": c.email,
                                      "skills": c.skills, "total_exp": float(c.total_exp) if c.total_exp is not None else None}
def _app_dict(a: Application): return {"id": str(a.id), "job_id": str(a.job_id), "candidate_id": str(a.candidate_id), "stage": a.stage}


# ── clients ──────────────────────────────────────────────────────
@router.post("/clients")
def create_client(body: ClientIn, ctx: RequestContext = Depends(get_current_context),
                  db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    obj = Client(tenant_id=_tid(ctx), business_unit_id=BU, name=body.name, industry=body.industry)
    db.add(obj); db.commit(); db.refresh(obj)
    res = _client_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


@router.get("/clients")
def list_clients(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    rows = db.execute(select(Client).where(Client.tenant_id == _tid(ctx), Client.business_unit_id == BU,
                                           Client.deleted_at.is_(None)).order_by(Client.created_at.desc())).scalars().all()
    return [_client_dict(c) for c in rows]


# ── candidates (tenant-scoped) ───────────────────────────────────
@router.post("/candidates")
def create_candidate(body: CandidateIn, ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    obj = Candidate(tenant_id=_tid(ctx), full_name=body.full_name, email=body.email, phone=body.phone,
                    pan=body.pan, skills=body.skills, total_exp=body.total_exp)
    db.add(obj); db.commit(); db.refresh(obj)
    res = _cand_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


@router.get("/candidates")
def list_candidates(q: str | None = Query(default=None), ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    stmt = select(Candidate).where(Candidate.tenant_id == _tid(ctx), Candidate.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Candidate.full_name.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Candidate.created_at.desc()).limit(50)).scalars().all()
    return [_cand_dict(c) for c in rows]


# ── jobs ─────────────────────────────────────────────────────────
@router.post("/jobs")
def create_job(body: JobIn, ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    obj = Job(tenant_id=_tid(ctx), business_unit_id=BU, title=body.title, client_id=body.client_id,
              jd_text=body.jd_text, skills=body.skills, min_exp=body.min_exp, max_exp=body.max_exp)
    db.add(obj); db.commit(); db.refresh(obj)
    res = _job_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


@router.get("/jobs")
def list_jobs(status: str | None = Query(default=None), ctx: RequestContext = Depends(get_current_context),
              db: Session = Depends(get_db)):
    stmt = select(Job).where(Job.tenant_id == _tid(ctx), Job.business_unit_id == BU, Job.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Job.status == status)
    rows = db.execute(stmt.order_by(Job.created_at.desc())).scalars().all()
    return [_job_dict(j) for j in rows]


@router.get("/jobs/{job_id}/pipeline")
def job_pipeline(job_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    job = db.execute(select(Job).where(Job.id == job_id, Job.tenant_id == _tid(ctx),
                                       Job.business_unit_id == BU)).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
    apps = db.execute(
        select(Application, Candidate)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id, Application.tenant_id == _tid(ctx),
               Application.business_unit_id == BU, Application.deleted_at.is_(None))
    ).all()
    by_stage: dict[str, list] = {s: [] for s in TRANSITIONS}
    for a, cand in apps:
        by_stage[a.stage].append({**_app_dict(a), "candidate": _cand_dict(cand)})
    return {"job": _job_dict(job), "stages": by_stage}


# ── applications ─────────────────────────────────────────────────
@router.post("/applications")
def create_application(body: ApplicationIn, ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    # Validate job + candidate belong to this tenant (job also to STAFFING).
    job = db.execute(select(Job).where(Job.id == body.job_id, Job.tenant_id == _tid(ctx),
                                       Job.business_unit_id == BU)).scalar_one_or_none()
    cand = db.execute(select(Candidate).where(Candidate.id == body.candidate_id,
                                              Candidate.tenant_id == _tid(ctx))).scalar_one_or_none()
    if job is None or cand is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job or candidate not found"})
    existing = db.execute(select(Application).where(Application.job_id == body.job_id,
                                                   Application.candidate_id == body.candidate_id)).scalar_one_or_none()
    if existing is not None:
        return _app_dict(existing)  # idempotent on the natural key
    obj = Application(tenant_id=_tid(ctx), business_unit_id=BU, job_id=body.job_id,
                      candidate_id=body.candidate_id, stage="sourced",
                      owner_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(obj); db.commit(); db.refresh(obj)
    res = _app_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


@router.patch("/applications/{app_id}/stage")
def change_stage(app_id: uuid.UUID, body: StageIn, ctx: RequestContext = Depends(get_current_context),
                 db: Session = Depends(get_db)):
    _require_staff(ctx)
    app = db.execute(select(Application).where(Application.id == app_id, Application.tenant_id == _tid(ctx),
                                              Application.business_unit_id == BU)).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Application not found"})
    if body.stage not in TRANSITIONS:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "Unknown stage"})
    if body.stage not in TRANSITIONS[app.stage]:
        raise HTTPException(status_code=409,
                            detail={"code": "ILLEGAL_TRANSITION", "message": f"Cannot move {app.stage} → {body.stage}"})
    app.stage = body.stage
    db.commit()
    return _app_dict(app)


# ── employer overview read-model ─────────────────────────────────
@router.get("/client-portal/overview")
def employer_overview(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    tid = _tid(ctx)

    def _count(stmt):
        return db.execute(stmt).scalar_one()

    open_jobs = _count(select(func.count()).select_from(Job).where(
        Job.tenant_id == tid, Job.business_unit_id == BU, Job.status == "open", Job.deleted_at.is_(None)))
    in_pipeline = _count(select(func.count()).select_from(Application).where(
        Application.tenant_id == tid, Application.business_unit_id == BU, Application.deleted_at.is_(None),
        Application.stage.notin_(["placed", "rejected"])))
    interviews = _count(select(func.count()).select_from(Application).where(
        Application.tenant_id == tid, Application.business_unit_id == BU, Application.stage == "interview"))
    placements = _count(select(func.count()).select_from(Application).where(
        Application.tenant_id == tid, Application.business_unit_id == BU, Application.stage == "placed"))

    funnel_rows = db.execute(
        select(Application.stage, func.count()).where(
            Application.tenant_id == tid, Application.business_unit_id == BU, Application.deleted_at.is_(None))
        .group_by(Application.stage)
    ).all()
    counts = {s: 0 for s in TRANSITIONS}
    for stage, n in funnel_rows:
        counts[stage] = n
    funnel = [{"label": s.title(), "value": counts[s]} for s in
              ["screened", "assessed", "submitted", "interview", "offer"]]

    recent = db.execute(
        select(Application, Candidate, Job)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Application.tenant_id == tid, Application.business_unit_id == BU, Application.deleted_at.is_(None))
        .order_by(Application.updated_at.desc()).limit(8)
    ).all()
    pipeline = [{"id": str(a.id), "candidate": cand.full_name, "job": job.title, "stage": a.stage}
                for a, cand, job in recent]

    return {"openJobs": open_jobs, "inPipeline": in_pipeline, "interviews": interviews,
            "placements": placements, "funnel": funnel, "pipeline": pipeline}
