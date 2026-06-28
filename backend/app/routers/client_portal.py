"""Client self-service portal (Task 5) — STRICTLY scoped to the session's client_id.

Every read goes through TenantScopedRepo.base_query, which nests the client_id
filter under tenant_id+BU (the base-layer guard proven by test_client_isolation).
`_require_client` ensures only a bound client session reaches these endpoints; staff
endpoints separately reject client sessions. Read-mostly; the two writes (submission
feedback, post a job) verify the target is within the client's own scope first.
"""
from __future__ import annotations

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
from ..models_staffing import Application, Candidate, Interview, Job, Offer, Submission
from ..repositories import TenantScopedRepo

router = APIRouter()
BU = "STAFFING"
APPLICATION_STAGES = ("sourced", "screened", "assessed", "submitted", "interview", "offer", "placed", "rejected", "on_hold")


def _require_client(ctx: RequestContext = Depends(get_current_context)) -> RequestContext:
    """Only a bound client-portal session (active client_users → JWT client_id) may
    use these endpoints. Staff/admin sessions have no client_id → 403 here."""
    if not ctx.client_id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Client portal access required"})
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
    """The client's candidates by pipeline stage (sourced→…→placed)."""
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
    obj = Job(tenant_id=uuid.UUID(str(ctx.tenant_id)), business_unit_id=BU,
              client_id=uuid.UUID(str(ctx.client_id)), title=body.title, jd_text=body.jd_text,
              skills=body.skills, min_exp=body.min_exp, max_exp=body.max_exp, status="open")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "client.post_job", "job", obj.id, after={"title": body.title})
    db.commit()
    res = {"id": str(obj.id), "title": obj.title, "status": obj.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res
