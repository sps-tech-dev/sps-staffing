"""Client self-service portal (Task 5) — STRICTLY scoped to the session's client_id.

Every read goes through TenantScopedRepo.base_query, which nests the client_id
filter under tenant_id+BU (the base-layer guard proven by test_client_isolation).
`_require_client` ensures only a bound client session reaches these endpoints; staff
endpoints separately reject client sessions. Read-mostly; the two writes (submission
feedback, post a job) verify the target is within the client's own scope first.
"""
from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models import ClientUser, User
from ..models_staffing import (APPLICATION_STAGES, Application, Candidate, Interview,
                               Job, Offer, Submission)
from ..repositories import TenantScopedRepo
from ..security import hash_password
from ..validation import validate_email, validate_password

router = APIRouter()
BU = "STAFFING"
# B.5-fix: the old LOCAL copy of APPLICATION_STAGES (dead pre-B.5 vocabulary)
# shadowed the models constant — the client pipeline view pre-seeded dead-stage
# buckets. Import the vocabulary owner instead; never re-declare it locally.


def _require_client(ctx: RequestContext = Depends(get_current_context)) -> RequestContext:
    """Only a bound client-portal session (active client_users → JWT client_id) may
    use these endpoints. Staff/admin sessions have no client_id → 403 here."""
    if not ctx.client_id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Client portal access required"})
    return ctx


def _require_client_admin(ctx: RequestContext = Depends(_require_client)) -> RequestContext:
    """Offer-write + team + reassign are HR-only. A client_manager (hiring manager) is a
    valid client session (passes _require_client) but is READ-ONLY on offers and cannot
    manage teammates / reassign jobs → 403. The gate is ctx.client_role from the JWT."""
    if ctx.client_role != "client_admin":
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN", "message": "HR (client admin) access required"})
    return ctx


def _repo(db, ctx):
    return TenantScopedRepo(db, ctx)


def _cand_names(db, repo, cand_ids):
    if not cand_ids:
        return {}
    rows = db.execute(repo.base_query(Candidate).where(Candidate.id.in_(cand_ids))).scalars().all()
    return {c.id: c.full_name for c in rows}


def _job_titles(db, repo, job_ids):
    if not job_ids:
        return {}
    rows = db.execute(repo.base_query(Job).where(Job.id.in_(job_ids))).scalars().all()
    return {j.id: j.title for j in rows}


@router.get("/overview")
def overview(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    repo = _repo(db, ctx)
    jobs = [j for j in repo.scoped_all(Job) if j.deleted_at is None]
    apps = [a for a in repo.scoped_all(Application) if a.deleted_at is None]
    interviews = [i for i in repo.scoped_all(Interview) if i.deleted_at is None]
    offers = [o for o in repo.scoped_all(Offer) if o.deleted_at is None]
    funnel = {s: 0 for s in APPLICATION_STAGES}
    for a in apps:
        funnel[a.stage] = funnel.get(a.stage, 0) + 1
    return {
        "open_jobs": sum(1 for j in jobs if j.status == "open"),
        "in_pipeline": len(apps),
        "interviews": sum(1 for i in interviews if i.status == "scheduled"),
        "offers": len(offers),
        "funnel": [{"label": s, "value": funnel.get(s, 0)} for s in APPLICATION_STAGES],
    }


@router.get("/jobs")
def jobs(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    repo = _repo(db, ctx)
    rows = [j for j in repo.scoped_all(Job) if j.deleted_at is None]
    return [{"id": str(j.id), "title": j.title, "status": j.status, "skills": j.skills,
             "min_exp": j.min_exp, "max_exp": j.max_exp} for j in rows]


@router.get("/pipeline")
def pipeline(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    """The client's candidates by pipeline stage (applied→…→paid, B.5 vocabulary)."""
    repo = _repo(db, ctx)
    apps = [a for a in repo.scoped_all(Application) if a.deleted_at is None]
    names = _cand_names(db, repo, {a.candidate_id for a in apps})
    titles = _job_titles(db, repo, {a.job_id for a in apps})
    stages = {s: [] for s in APPLICATION_STAGES}
    for a in apps:
        stages.setdefault(a.stage, []).append({
            "id": str(a.id), "candidate": names.get(a.candidate_id, "—"),
            "job": titles.get(a.job_id, "—"), "stage": a.stage})
    return {"stages": stages}


@router.get("/submissions")
def submissions(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    """Candidates the recruiters submitted to this client (with their pipeline stage)."""
    repo = _repo(db, ctx)
    subs = [s for s in repo.scoped_all(Submission) if s.deleted_at is None]
    apps = {a.id: a for a in repo.scoped_all(Application)}
    names = _cand_names(db, repo, {a.candidate_id for a in apps.values()})
    titles = _job_titles(db, repo, {a.job_id for a in apps.values()})
    out = []
    for s in subs:
        a = apps.get(s.application_id)
        out.append({"id": str(s.id), "status": s.status, "client_feedback": s.client_feedback,
                    "candidate": names.get(a.candidate_id) if a else None,
                    "job": titles.get(a.job_id) if a else None,
                    "stage": a.stage if a else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None})
    return out


@router.get("/interviews")
def interviews(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    repo = _repo(db, ctx)
    rows = [i for i in repo.scoped_all(Interview) if i.deleted_at is None]
    apps = {a.id: a for a in repo.scoped_all(Application)}
    names = _cand_names(db, repo, {a.candidate_id for a in apps.values()})
    return [{"id": str(i.id), "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
             "mode": i.mode, "status": i.status,
             "candidate": names.get(apps[i.application_id].candidate_id) if i.application_id in apps else None}
            for i in rows]


@router.get("/offers")
def offers(ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    repo = _repo(db, ctx)
    rows = [o for o in repo.scoped_all(Offer) if o.deleted_at is None]
    apps = {a.id: a for a in repo.scoped_all(Application)}
    names = _cand_names(db, repo, {a.candidate_id for a in apps.values()})
    return [{"id": str(o.id), "status": o.status, "ctc": float(o.ctc) if o.ctc is not None else None,
             "joining_date": o.joining_date.isoformat() if o.joining_date else None,
             "candidate": names.get(apps[o.application_id].candidate_id) if o.application_id in apps else None}
            for o in rows]


# ── writes (client-scoped) ───────────────────────────────────────
class FeedbackIn(BaseModel):
    decision: str   # 'approve' (shortlist) or 'reject'
    note: str | None = None

    @field_validator("decision")
    @classmethod
    def _d(cls, v):
        if v not in ("approve", "reject"):
            raise ValueError("decision must be 'approve' or 'reject'")
        return v


@router.post("/submissions/{submission_id}/feedback")
def submission_feedback(submission_id: uuid.UUID, body: FeedbackIn,
                        ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db)):
    """Client approves (shortlists) or rejects a submitted candidate. The submission
    must be in THIS client's scope (base_query) or it is invisible → 404."""
    repo = _repo(db, ctx)
    s = db.execute(repo.base_query(Submission).where(Submission.id == submission_id,
                                                     Submission.deleted_at.is_(None))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Submission not found"})
    before = {"status": s.status}
    s.status = "shortlisted" if body.decision == "approve" else "rejected"
    if body.note is not None:
        s.client_feedback = body.note
    db.flush()
    write_audit(db, ctx, "client.submission_feedback", "submission", s.id, before=before, after={"status": s.status})
    db.commit()
    return {"id": str(s.id), "status": s.status, "client_feedback": s.client_feedback}


class JobIn(BaseModel):
    title: str
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


@router.post("/jobs")
def post_job(body: JobIn, ctx: RequestContext = Depends(_require_client), db: Session = Depends(get_db),
             idempotency_key: str | None = Header(default=None)):
    """Client posts a new job → lands in the tenant recruiters' queue, owned by THIS
    client (client_id forced from the session, never from the body)."""
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    # owner_user_id = the posting client user → the manager↔manager isolation key. HR
    # (client_admin) posting also stamps themselves as owner; they can reassign later.
    obj = Job(tenant_id=uuid.UUID(str(ctx.tenant_id)), business_unit_id=BU,
              client_id=uuid.UUID(str(ctx.client_id)),
              owner_user_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None,
              title=body.title, jd_text=body.jd_text,
              skills=body.skills, min_exp=body.min_exp, max_exp=body.max_exp, status="open")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "client.post_job", "job", obj.id, after={"title": body.title})
    db.commit()
    res = {"id": str(obj.id), "title": obj.title, "status": obj.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


# ── OFFER WRITE — HR (client_admin) ONLY ─────────────────────────────
# Reads (GET /offers) stay open to BOTH roles; only release / joining-date are gated.
# A client_manager hitting these gets 403 (read-only offer card on their own job).
class OfferReleaseIn(BaseModel):
    joining_date: datetime.date            # releasing an offer commits a joining date
    ctc: float | None = None               # optional HR adjustment to the proposed CTC

    @field_validator("ctc")
    @classmethod
    def _ctc(cls, v):
        if v is not None and v < 0:
            raise ValueError("CTC must be non-negative")
        return v


def _offer_in_scope(db, repo, offer_id):
    o = db.execute(repo.base_query(Offer).where(
        Offer.id == offer_id, Offer.deleted_at.is_(None))).scalar_one_or_none()
    if o is None:
        # Out of the client's scope (incl. a manager's non-owned job) → invisible → 404.
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Offer not found"})
    return o


@router.post("/offers/{offer_id}/release")
def release_offer(offer_id: uuid.UUID, body: OfferReleaseIn,
                  ctx: RequestContext = Depends(_require_client_admin), db: Session = Depends(get_db),
                  idempotency_key: str | None = Header(default=None)):
    """HR releases a DRAFT offer to the candidate + commits the joining date. The offer
    must be in this client's scope (404 otherwise). draft → released only."""
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    repo = _repo(db, ctx)
    o = _offer_in_scope(db, repo, offer_id)
    if o.status != "draft":
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_STATE", "message": f"Offer is already {o.status}"})
    before = {"status": o.status, "joining_date": o.joining_date.isoformat() if o.joining_date else None}
    o.joining_date = body.joining_date
    if body.ctc is not None:
        o.ctc = body.ctc
    o.status = "released"
    db.flush()
    write_audit(db, ctx, "client.release_offer", "offer", o.id, before=before,
                after={"status": o.status, "joining_date": o.joining_date.isoformat()})
    db.commit()
    res = {"id": str(o.id), "status": o.status,
           "ctc": float(o.ctc) if o.ctc is not None else None,
           "joining_date": o.joining_date.isoformat()}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


class JoiningDateIn(BaseModel):
    joining_date: datetime.date


@router.patch("/offers/{offer_id}/joining-date")
def set_joining_date(offer_id: uuid.UUID, body: JoiningDateIn,
                     ctx: RequestContext = Depends(_require_client_admin), db: Session = Depends(get_db)):
    """HR adjusts a released offer's joining date (not after the candidate accepts)."""
    repo = _repo(db, ctx)
    o = _offer_in_scope(db, repo, offer_id)
    if o.status not in ("draft", "released"):
        raise HTTPException(status_code=409, detail={
            "code": "INVALID_STATE", "message": f"Cannot change joining date on a {o.status} offer"})
    before = {"joining_date": o.joining_date.isoformat() if o.joining_date else None}
    o.joining_date = body.joining_date
    db.flush()
    write_audit(db, ctx, "client.set_joining_date", "offer", o.id, before=before,
                after={"joining_date": o.joining_date.isoformat()})
    db.commit()
    return {"id": str(o.id), "status": o.status, "joining_date": o.joining_date.isoformat()}


# ── TEAM (teammate management) — HR (client_admin) ONLY ──────────────
def _active_client_user(db, ctx, user_id):
    """An ACTIVE client_users row binding `user_id` to THIS session's client (or None)."""
    return db.execute(select(ClientUser).where(
        ClientUser.tenant_id == uuid.UUID(str(ctx.tenant_id)),
        ClientUser.client_id == uuid.UUID(str(ctx.client_id)),
        ClientUser.user_id == user_id, ClientUser.status == "active")).scalar_one_or_none()


@router.get("/team")
def team(ctx: RequestContext = Depends(_require_client_admin), db: Session = Depends(get_db)):
    """HR lists the client's portal users (HR + hiring managers) with their role."""
    rows = db.execute(
        select(ClientUser, User).join(User, User.id == ClientUser.user_id).where(
            ClientUser.tenant_id == uuid.UUID(str(ctx.tenant_id)),
            ClientUser.client_id == uuid.UUID(str(ctx.client_id)),
            ClientUser.status == "active").order_by(ClientUser.created_at)).all()
    return [{"user_id": str(cu.user_id), "email": str(u.email), "name": u.full_name,
             "role": cu.role, "is_self": str(cu.user_id) == str(ctx.user_id)}
            for cu, u in rows]


class TeammateIn(BaseModel):
    email: str
    full_name: str
    initial_password: str
    role: str = "client_manager"          # default = hiring manager

    @field_validator("email")
    @classmethod
    def _e(cls, v):
        return validate_email(v)

    @field_validator("initial_password")
    @classmethod
    def _p(cls, v):
        return validate_password(v)

    @field_validator("role")
    @classmethod
    def _r(cls, v):
        if v not in ("client_admin", "client_manager"):
            raise ValueError("role must be client_admin or client_manager")
        return v


@router.post("/team")
def add_teammate(body: TeammateIn, ctx: RequestContext = Depends(_require_client_admin),
                 db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """HR invites a teammate: creates the login user (active) + an ACTIVE client_users
    binding to THIS client with the chosen role. Same tenant+client scope as HR."""
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    tid = uuid.UUID(str(ctx.tenant_id))
    if db.execute(select(User).where(User.tenant_id == tid, User.email == body.email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail={
            "code": "USER_EXISTS", "message": "A user with this email already exists"})
    user = User(tenant_id=tid, email=body.email, password_hash=hash_password(body.initial_password),
                full_name=body.full_name, status="active")
    db.add(user); db.flush()
    db.add(ClientUser(tenant_id=tid, user_id=user.id, client_id=uuid.UUID(str(ctx.client_id)),
                      status="active", role=body.role))
    write_audit(db, ctx, "client.add_teammate", "user", user.id,
                after={"email": body.email, "role": body.role})
    db.commit()
    res = {"user_id": str(user.id), "email": body.email, "role": body.role}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


# ── JOB REASSIGNMENT — HR (client_admin) ONLY ────────────────────────
class ReassignIn(BaseModel):
    owner_user_id: uuid.UUID


@router.post("/jobs/{job_id}/reassign")
def reassign_job(job_id: uuid.UUID, body: ReassignIn,
                 ctx: RequestContext = Depends(_require_client_admin), db: Session = Depends(get_db)):
    """HR reassigns a job to a different hiring manager. Cascades owner_user_id onto the
    job's whole pipeline (applications/submissions/offers/interviews) so the new owner
    sees it and the old one no longer does. New owner must be an active user of THIS
    client. Audited. A manager cannot reach this (403)."""
    repo = _repo(db, ctx)   # client_admin → no owner filter → all the client's jobs
    job = db.execute(repo.base_query(Job).where(
        Job.id == job_id, Job.deleted_at.is_(None))).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
    if _active_client_user(db, ctx, body.owner_user_id) is None:
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_OWNER", "message": "New owner must be an active user of this client"})
    before = {"owner_user_id": str(job.owner_user_id) if job.owner_user_id else None}
    job.owner_user_id = body.owner_user_id
    # Cascade onto the dependent pipeline rows (scoped to this client via base_query).
    apps = db.execute(repo.base_query(Application).where(
        Application.job_id == job_id)).scalars().all()
    app_ids = [a.id for a in apps]
    for a in apps:
        a.owner_user_id = body.owner_user_id
    if app_ids:
        for model in (Submission, Offer, Interview):
            for row in db.execute(repo.base_query(model).where(
                    model.application_id.in_(app_ids))).scalars().all():
                row.owner_user_id = body.owner_user_id
    db.flush()
    write_audit(db, ctx, "client.reassign_job", "job", job.id, before=before,
                after={"owner_user_id": str(body.owner_user_id)})
    db.commit()
    return {"id": str(job.id), "owner_user_id": str(body.owner_user_id),
            "pipeline_reassigned": len(app_ids)}
