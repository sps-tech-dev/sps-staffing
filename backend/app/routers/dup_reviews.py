"""Duplicate-review queue + merge/dismiss (B.3). Staff-gated, tenant-scoped;
client-portal sessions are rejected (403) — dup reviews are internal.

Merge integrity (one transaction, audited, reversible-trail, NEVER hard-deletes):
  survivor = matched_candidate_id (the pre-existing record)
  loser    = candidate_id         (the incoming record, create-then-flag)

  - Non-colliding loser applications are repointed to the survivor. Their children
    (submissions/offers/interviews) carry application_id only, so they follow
    automatically — they have no candidate_id column.
  - APPLICATION COLLISION (both applied to the same job): UNIQUE(job_id,
    candidate_id) covers soft-deleted rows too, so the redundant row can never be
    repointed. Rule: the surviving application ROW is always the survivor's; if
    the loser's application is FURTHER ALONG (stage rank, tie → earlier
    created_at), its stage is adopted onto the survivor's row. The loser's row is
    archived IN PLACE (soft-deleted, candidate_id unchanged) with its children
    still attached — traceable, nothing lost.
  - vendor_submissions.candidate_id is repointed (no unique).
  - candidate_timeline + shared.consents are APPEND-ONLY (sps_app has no UPDATE,
    by design since B.2 / the sps_app role) — they are NOT repointed. The loser
    shell is retained (soft-deleted, blind indexes cleared like erasure) so those
    immutable rows keep a valid anchor; Merged/MergedInto events cross-link the
    two records.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models_staffing import Application, Candidate, CandidateDupReview, VendorSubmission
from ..pipeline import STAGE_RANK, adopt_stage_on_merge
from ..timeline import EventType, emit_timeline
from .staffing import _require_staff, _tid

router = APIRouter()

# STAGE_RANK (further-along = higher; tie → earlier created_at wins) lives in
# app/pipeline.py since B.5 — the single owner of the stage vocabulary.


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _review_or_404(db: Session, ctx: RequestContext, review_id: int) -> CandidateDupReview:
    r = db.execute(select(CandidateDupReview).where(
        CandidateDupReview.id == review_id,
        CandidateDupReview.tenant_id == _tid(ctx))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Review not found"})
    return r


def _require_pending(r: CandidateDupReview):
    if r.status != "pending":
        raise HTTPException(status_code=409, detail={
            "code": "REVIEW_NOT_PENDING", "message": f"Review already {r.status}"})


def _review_dict(r: CandidateDupReview, names: dict | None = None) -> dict:
    return {"id": r.id, "candidate_id": str(r.candidate_id),
            "matched_candidate_id": str(r.matched_candidate_id),
            "candidate_name": (names or {}).get(r.candidate_id),
            "matched_candidate_name": (names or {}).get(r.matched_candidate_id),
            "match_type": r.match_type, "score": float(r.score), "status": r.status,
            "signal": (r.incoming_payload or {}).get("signal"),
            "created_at": r.created_at.isoformat() if r.created_at else None}


@router.get("/candidates/dup-reviews")
def list_dup_reviews(status: str | None = Query(default=None),
                     limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
                     ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db)):
    """Pending-first review queue (then newest)."""
    _require_staff(ctx)
    stmt = select(CandidateDupReview).where(CandidateDupReview.tenant_id == _tid(ctx))
    if status:
        stmt = stmt.where(CandidateDupReview.status == status)
    rows = db.execute(
        stmt.order_by((CandidateDupReview.status != "pending").asc(),
                      CandidateDupReview.created_at.desc())
        .limit(limit).offset(offset)).scalars().all()
    ids = {r.candidate_id for r in rows} | {r.matched_candidate_id for r in rows}
    names = {c.id: c.full_name for c in db.execute(
        select(Candidate).where(Candidate.tenant_id == _tid(ctx),
                                Candidate.id.in_(ids))).scalars()} if ids else {}
    return [_review_dict(r, names) for r in rows]


@router.post("/candidates/dup-reviews/{review_id}/dismiss")
def dismiss_dup_review(review_id: int, ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db),
                       idempotency_key: str | None = Header(default=None)):
    """Not a duplicate: BOTH candidates remain distinct people (create-then-flag —
    the incoming candidate was already created, so nothing else changes)."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    r = _review_or_404(db, ctx, review_id)
    _require_pending(r)
    r.status = "dismissed"
    r.reviewed_by = uuid.UUID(str(ctx.user_id)) if ctx.user_id else None
    r.reviewed_at = _now()
    write_audit(db, ctx, "candidate.dup_dismiss", "candidate_dup_review", None,
                after={"review_id": r.id, "candidate_id": str(r.candidate_id),
                       "matched_candidate_id": str(r.matched_candidate_id)})
    db.commit()
    res = _review_dict(r)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.post("/candidates/dup-reviews/{review_id}/merge")
def merge_dup_review(review_id: int, ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db),
                     idempotency_key: str | None = Header(default=None)):
    """Confirmed duplicate: merge the incoming candidate (loser) into the matched
    existing candidate (survivor). One transaction; see module docstring for the
    integrity rules."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    r = _review_or_404(db, ctx, review_id)
    _require_pending(r)

    tid = _tid(ctx)
    survivor = db.execute(select(Candidate).where(
        Candidate.id == r.matched_candidate_id, Candidate.tenant_id == tid,
        Candidate.deleted_at.is_(None))).scalar_one_or_none()
    loser = db.execute(select(Candidate).where(
        Candidate.id == r.candidate_id, Candidate.tenant_id == tid,
        Candidate.deleted_at.is_(None))).scalar_one_or_none()
    if survivor is None or loser is None:
        raise HTTPException(status_code=409, detail={
            "code": "MERGE_TARGET_GONE",
            "message": "Survivor or duplicate candidate no longer active"})

    # ── applications: collision-aware repoint (unique(job_id, candidate_id)
    #    covers soft-deleted rows, so redundant rows are archived IN PLACE) ──
    surv_apps_by_job = {a.job_id: a for a in db.execute(select(Application).where(
        Application.tenant_id == tid, Application.candidate_id == survivor.id)).scalars()}
    loser_apps = db.execute(select(Application).where(
        Application.tenant_id == tid, Application.candidate_id == loser.id)).scalars().all()

    repointed, archived = [], []
    for la in loser_apps:
        sa_ = surv_apps_by_job.get(la.job_id)
        if sa_ is None:
            la.candidate_id = survivor.id            # no collision → repoint
            repointed.append(str(la.id))
            continue
        # collision: keep the further-along stage on the SURVIVOR'S row
        la_key = (STAGE_RANK.get(la.stage, 0), -(la.created_at or _now()).timestamp())
        sa_key = (STAGE_RANK.get(sa_.stage, 0), -(sa_.created_at or _now()).timestamp())
        if la_key > sa_key:
            adopt_stage_on_merge(sa_, la.stage)      # documented exception in pipeline.py
        if la.deleted_at is None:
            la.deleted_at = _now()                   # archive loser's row in place
        archived.append(str(la.id))

    # ── vendor_submissions: plain repoint (no unique) ──
    vs = db.execute(update(VendorSubmission)
                    .where(VendorSubmission.tenant_id == tid,
                           VendorSubmission.candidate_id == loser.id)
                    .values(candidate_id=survivor.id))
    vendor_repointed = vs.rowcount or 0

    # candidate_timeline + shared.consents: APPEND-ONLY → NOT repointed (see docstring).

    # ── retire the loser shell: clear unique slots (mirror erasure), soft-delete ──
    loser.phone_bidx = None
    loser.pan_bidx = None
    loser.deleted_at = _now()

    r.status = "merged"
    r.reviewed_by = uuid.UUID(str(ctx.user_id)) if ctx.user_id else None
    r.reviewed_at = _now()

    summary = {"survivor": str(survivor.id), "loser": str(loser.id), "review_id": r.id,
               "applications_repointed": repointed, "applications_archived": archived,
               "vendor_submissions_repointed": vendor_repointed}
    emit_timeline(db, candidate_id=loser.id, event_type=EventType.MERGED_INTO,
                  payload={"merged_into": str(survivor.id), "review_id": r.id}, ctx=ctx)
    emit_timeline(db, candidate_id=survivor.id, event_type=EventType.MERGED,
                  payload={"merged_from": str(loser.id), "review_id": r.id,
                           "applications_repointed": len(repointed),
                           "applications_archived": len(archived)}, ctx=ctx)
    write_audit(db, ctx, "candidate.merge", "candidate", survivor.id,
                before={"loser": str(loser.id), "survivor": str(survivor.id)}, after=summary)
    db.commit()

    res = {**_review_dict(r), "merge": summary}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res
