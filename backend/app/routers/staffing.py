"""Staffing vertical endpoints (Part 5): clients, candidates, jobs, applications,
pipeline + the employer overview read-model. All authenticated, tenant-scoped;
two-axis tables also scoped to business_unit_id='STAFFING'. Candidates are
tenant-scoped (talent pool). Writes honor Idempotency-Key and require a staff role.
"""
from __future__ import annotations

import datetime
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..crypto import blind_index
from ..db import get_db
from ..dedup import flag_if_fuzzy_dup
from ..models import Consent
from .. import pipeline
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models_staffing import (Application, Candidate, CandidateTimeline, Client,
                               InternalEvaluation, Job)
from ..timeline import EventType, emit_timeline
from ..validation import normalize_phone, validate_email, validate_name, validate_pan

router = APIRouter()
BU = "STAFFING"

STAFF_ROLES = {"owner", "super_admin", "admin", "business_manager", "manager",
               "recruiter", "coordinator", "employee", "client"}

# Pipeline transitions live EXCLUSIVELY in app/pipeline.py since B.5 — the old
# TRANSITIONS dict is gone; every stage change goes through pipeline.transition().


def _require_staff(ctx: RequestContext):
    # A client-portal session (client_id bound) is NEVER staff — it may use only the
    # client-scoped /api/client/* endpoints, never these tenant-wide staff queries.
    if ctx.client_id is not None or not (set(ctx.roles) & STAFF_ROLES):
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
    # PII (Part 10): phone/pan are encrypted at rest (EncryptedStr) + carry a
    # deterministic blind index for dedup. We do NOT write the legacy plaintext
    # columns anymore (dropped in the contract migration). A bidx unique violation
    # = Part 19 duplicate (same person already in this tenant's pool).
    obj = Candidate(tenant_id=_tid(ctx), full_name=body.full_name, email=body.email,
                    phone_enc=body.phone, pan_enc=body.pan,
                    phone_bidx=blind_index(body.phone), pan_bidx=blind_index(body.pan),
                    skills=body.skills, total_exp=body.total_exp)
    db.add(obj)
    try:
        db.flush()  # exact dup (blind-index unique) surfaces here → 409, unchanged
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "code": "DUPLICATE_CANDIDATE",
            "message": "A candidate with this phone or PAN already exists in your talent pool",
        })
    # B.3 fuzzy dup scan (create-then-flag), same txn as the create
    flag_if_fuzzy_dup(db, tenant_id=_tid(ctx), candidate=obj, skills=body.skills,
                      source="staff_create")
    db.commit()
    db.refresh(obj)
    res = _cand_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


@router.get("/candidates")
def list_candidates(q: str | None = Query(default=None), ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    stmt = select(Candidate).where(Candidate.tenant_id == _tid(ctx), Candidate.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Candidate.full_name.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Candidate.created_at.desc()).limit(50)).scalars().all()
    return [_cand_dict(c) for c in rows]


@router.get("/candidates/search")
def search_candidates(q: str | None = Query(default=None),
                      skills: str | None = Query(default=None, description="CSV of required skills (@> all)"),
                      exp_min: float | None = Query(default=None, ge=0),
                      exp_max: float | None = Query(default=None, ge=0),
                      ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db)):
    """Talent-pool search (B.4): Postgres FTS over the maintained search_doc
    (name weight A > skills B > resume_text C, 'simple' config) + structured
    filters. STAFF-ONLY — clients reach candidates only via their own scoped
    submissions, never the pool. Returns MASKED cards (no email/phone/pan).

    location / notice_period filters: columns absent on candidates — skipped
    until those fields exist (same discipline as ProfileUpdate in B.2).
    """
    _require_staff(ctx)
    stmt = select(Candidate).where(Candidate.tenant_id == _tid(ctx),
                                   Candidate.deleted_at.is_(None))
    tsq = None
    if q and q.strip():
        # websearch grammar: whitespace = AND, `or` = OR, -word = NOT, "..." = phrase.
        # The literal token AND is NOT an operator, and 'simple' has no stopwords, so
        # "Python AND AWS" would search for the word "and" — strip standalone ANDs
        # (identical semantics: whitespace already conjuncts).
        q_norm = re.sub(r"\bAND\b", " ", q.strip(), flags=re.IGNORECASE)
        tsq = func.websearch_to_tsquery("simple", q_norm)
        stmt = stmt.where(Candidate.search_doc.op("@@")(tsq))
    if skills:
        wanted = [s.strip() for s in skills.split(",") if s.strip()]
        if wanted:
            stmt = stmt.where(Candidate.skills.contains(wanted))  # @> (GIN ix_candidates_skills)
    if exp_min is not None:
        stmt = stmt.where(Candidate.total_exp >= exp_min)
    if exp_max is not None:
        stmt = stmt.where(Candidate.total_exp <= exp_max)
    if tsq is not None:
        stmt = stmt.order_by(func.ts_rank(Candidate.search_doc, tsq).desc(),
                             Candidate.created_at.desc())
    else:
        stmt = stmt.order_by(Candidate.created_at.desc())
    rows = db.execute(stmt.limit(50)).scalars().all()
    # masked cards — mirror the admin-list discipline: presence flags, never PII values
    return [{"id": str(c.id), "full_name": c.full_name, "skills": c.skills,
             "total_exp": float(c.total_exp) if c.total_exp is not None else None,
             "has_phone": c.phone_bidx is not None, "has_pan": c.pan_bidx is not None,
             "has_resume": c.resume_s3_key is not None} for c in rows]


@router.get("/candidates/{candidate_id}/timeline")
def candidate_timeline(candidate_id: uuid.UUID, event_type: str | None = Query(default=None),
                       ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db)):
    """Chronological (oldest-first) append-only history for a candidate (B.2).

    STAFF-ONLY: _require_staff also rejects client-portal sessions (client_id
    bound) — a client must never read a candidate's internal timeline.
    """
    _require_staff(ctx)
    cand = db.execute(select(Candidate).where(Candidate.id == candidate_id,
                                              Candidate.tenant_id == _tid(ctx))).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Candidate not found"})
    stmt = select(CandidateTimeline).where(CandidateTimeline.tenant_id == _tid(ctx),
                                           CandidateTimeline.candidate_id == candidate_id)
    if event_type:
        stmt = stmt.where(CandidateTimeline.event_type == event_type)
    rows = db.execute(stmt.order_by(CandidateTimeline.occurred_at.asc(),
                                    CandidateTimeline.id.asc())).scalars().all()
    return [{"id": r.id, "event_type": r.event_type, "payload": r.payload,
             "actor_id": str(r.actor_id) if r.actor_id else None,
             "occurred_at": r.occurred_at.isoformat()} for r in rows]


# ── jobs ─────────────────────────────────────────────────────────
@router.post("/jobs")
def create_job(body: JobIn, ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    obj = Job(tenant_id=_tid(ctx), business_unit_id=BU, title=body.title, client_id=body.client_id,
              jd_text=body.jd_text, skills=body.skills, min_exp=body.min_exp, max_exp=body.max_exp)
    db.add(obj); db.flush()
    write_audit(db, ctx, "job.create", "job", obj.id, after={"title": obj.title})
    db.commit(); db.refresh(obj)
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
                      candidate_id=body.candidate_id, client_id=job.client_id,
                      owner_user_id=job.owner_user_id, stage="applied",
                      owner_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(obj); db.flush()
    write_audit(db, ctx, "application.create", "application", obj.id,
                after={"job_id": str(body.job_id), "candidate_id": str(body.candidate_id), "stage": "applied"})
    emit_timeline(db, candidate_id=body.candidate_id, event_type=EventType.APPLICATION,
                  payload={"application_id": str(obj.id), "job_id": str(body.job_id),
                           "stage": "applied"}, ctx=ctx)
    db.commit(); db.refresh(obj)
    res = _app_dict(obj); store(str(ctx.tenant_id), idempotency_key, res); return res


def _app_or_404_here(db: Session, ctx: RequestContext, app_id: uuid.UUID) -> Application:
    app = db.execute(select(Application).where(Application.id == app_id, Application.tenant_id == _tid(ctx),
                                               Application.business_unit_id == BU,
                                               Application.deleted_at.is_(None))).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Application not found"})
    return app


class TransitionIn(BaseModel):
    to_stage: str
    expected_version: int
    reason: str | None = None


@router.post("/applications/{app_id}/transition")
def transition_application(app_id: uuid.UUID, body: TransitionIn,
                           ctx: RequestContext = Depends(get_current_context),
                           db: Session = Depends(get_db),
                           idempotency_key: str | None = Header(default=None)):
    """THE single public stage-change entry point (B.5). Optimistic-locked:
    expected_version must match or 409 STALE_STATE."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    app = _app_or_404_here(db, ctx, app_id)
    res = pipeline.transition(db, app, body.to_stage, ctx=ctx,
                              expected_version=body.expected_version, reason=body.reason)
    db.commit()
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.post("/applications/{app_id}/rtr")
def record_rtr_consent(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db),
                       idempotency_key: str | None = Header(default=None)):
    """Record Right-to-Represent consent for this application (unblocks the
    rtr_pending → submitted_to_client gate). Sets applications.rtr_consent_at/by
    AND appends the immutable shared.consents 'rtr' ledger row (DPDP trail)."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    app = _app_or_404_here(db, ctx, app_id)
    if app.rtr_consent_at is None:
        app.rtr_consent_at = datetime.datetime.now(datetime.timezone.utc)
        app.rtr_consent_by = uuid.UUID(str(ctx.user_id)) if ctx.user_id else None
        db.add(Consent(tenant_id=_tid(ctx), subject_candidate_id=app.candidate_id,
                       purpose="rtr", granted=True, policy_version="rtr-v1"))
        write_audit(db, ctx, "application.rtr_consent", "application", app.id,
                    after={"rtr": True, "candidate_id": str(app.candidate_id)})
        db.commit()
    res = {"id": str(app.id), "rtr_consent_at": app.rtr_consent_at.isoformat()}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


# (round, result) → target stage (B.6). Stage effects go through pipeline.transition()
# ONLY — the graph rejects out-of-order recording (e.g. R2 while at screening → 409),
# and the evaluation row rolls back with it (same txn).
EVAL_TARGETS = {
    (1, "pass"): ("aptitude_passed", None),
    (1, "fail"): ("aptitude_failed", None),
    (2, "pass"): ("internal_passed", None),
    (2, "fail"): ("dropped", "failed internal technical"),  # guard's drop-with-reason path
}


class EvaluationIn(BaseModel):
    round: int
    result: str
    notes: str | None = None
    expected_version: int | None = None  # optional CAS; defaults to the loaded version

    @field_validator("round")
    @classmethod
    def _r(cls, v):
        if v not in (1, 2):
            raise ValueError("round must be 1 (aptitude) or 2 (internal technical)")
        return v

    @field_validator("result")
    @classmethod
    def _res(cls, v):
        if v not in ("pass", "fail"):
            raise ValueError("result must be 'pass' or 'fail'")
        return v


@router.post("/applications/{app_id}/evaluations")
def record_evaluation(app_id: uuid.UUID, body: EvaluationIn,
                      ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db),
                      idempotency_key: str | None = Header(default=None)):
    """Record an internal evaluation round (B.6): R1 aptitude / R2 technical.
    Persists the evaluation row and drives the stage change through the B.5 guard
    in ONE transaction — an illegal transition rolls back the record too."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    app = _app_or_404_here(db, ctx, app_id)
    to_stage, reason = EVAL_TARGETS[(body.round, body.result)]

    ev = InternalEvaluation(tenant_id=_tid(ctx), business_unit_id=BU, application_id=app.id,
                            round=body.round, result=body.result, notes=body.notes,
                            evaluator_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(ev)
    # transition() raises on illegal moves/stale version BEFORE commit → ev rolls back.
    res = pipeline.transition(db, app, to_stage, ctx=ctx,
                              expected_version=body.expected_version or app.version,
                              reason=reason)
    if body.round == 1:
        # TestCompletion: B.6 wires the MANUAL R1 emitter; the B.7 automated engine
        # will be a second call site for the same event — no conflict.
        emit_timeline(db, candidate_id=app.candidate_id, event_type=EventType.TEST_COMPLETION,
                      payload={"application_id": str(app.id), "round": 1,
                               "result": body.result}, ctx=ctx)
    write_audit(db, ctx, "application.evaluation", "application", app.id,
                after={"round": body.round, "result": body.result, "to_stage": to_stage})
    db.commit()
    out = {"application_id": str(app.id), "round": body.round, "result": body.result,
           "stage": res["stage"], "version": res["version"], "evaluation_id": ev.id}
    store(str(ctx.tenant_id), idempotency_key, out)
    return out


@router.patch("/applications/{app_id}/stage")
def change_stage(app_id: uuid.UUID, body: StageIn, ctx: RequestContext = Depends(get_current_context),
                 db: Session = Depends(get_db)):
    """DEPRECATED shim (kept for the local frontend kanban): delegates to
    pipeline.transition() with last-write-wins version semantics (the loaded
    row's current version). Illegal moves still 409; nothing writes stage here."""
    _require_staff(ctx)
    app = _app_or_404_here(db, ctx, app_id)
    res = pipeline.transition(db, app, body.stage, ctx=ctx, expected_version=app.version)
    db.commit()
    return {**_app_dict(app), "stage": res["stage"]}


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
