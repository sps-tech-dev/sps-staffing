"""DPDP erasure engine — Stage 1: disable + anonymize + audit + approval gate.

Hybrid model (DECISIONS 2026-06-28):
  1. DISABLE immediately on request — soft-delete the principal's candidate(s)
     (instant access loss, reversible window). Runs at request time.
  2. On an explicit APPROVED transition — ANONYMIZE personal data irreversibly,
     while RETAINING de-identified legally-required records.
  3. AUTO-PURGE (timed hard-delete after a statutory retention period) — STUB ONLY,
     deletes NOTHING, blocked on legal retention numbers (GST/TDS/DPDP).
  4. Approval gate — normal erasure auto-approves; legal_hold is exempt and needs
     explicit manual approval.

Runs through `sps_app`: UPDATE candidates/users/dpdp_requests + INSERT audit are
allowed; it never UPDATE/DELETEs audit_logs/consents (append-only holds).
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, undefer

from .audit import write_audit
from .config import settings
from .context import RequestContext
from .models import DpdpRequest, User
from .models_staffing import Application, Candidate

log = logging.getLogger("sps.erasure")

# State machine
PENDING, APPROVED, PROCESSING, COMPLETED, REJECTED, LEGAL_HOLD = (
    "pending", "approved", "processing", "completed", "rejected", "legal_hold"
)
ERASED = "[erased]"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def under_legal_hold(db: Session, ctx: RequestContext, user: User) -> bool:
    """STUB for the legal-hold rule (open legal Q5). No hold rule defined yet → False.
    When legal defines it, return True for accounts under active hold/dispute so the
    request is exempt from auto-processing and needs explicit manual approval."""
    return False


def soft_delete_candidates(db: Session, ctx: RequestContext, email: str | None) -> int:
    """DISABLE immediately: set deleted_at on the principal's candidate(s). Reversible
    window — anonymization (irreversible) is separate and gated behind approval."""
    if not email:
        return 0
    res = db.execute(
        update(Candidate)
        .where(Candidate.tenant_id == uuid.UUID(str(ctx.tenant_id)),
               Candidate.email == email, Candidate.deleted_at.is_(None))
        .values(deleted_at=_now())
    )
    return res.rowcount or 0


def _delete_resume_objects(keys: list[str]) -> int:
    """Delete S3 resume objects. Today no upload code exists ⇒ keys is empty ⇒ no-op.
    When resume upload lands, the task role needs s3:DeleteObject + the bucket config
    fix (PENDING C5)."""
    if not keys:
        return 0
    deleted = 0
    try:
        import boto3
        s3 = boto3.client("s3", region_name=settings.aws_region)
        for k in keys:
            s3.delete_object(Bucket=settings.storage_bucket, Key=k)
            deleted += 1
    except Exception as e:  # noqa: BLE001 — never fail the erasure on S3; surface for follow-up
        log.error("resume S3 delete failed (needs s3:DeleteObject grant + bucket cfg, PENDING C5): %s", e)
    return deleted


def _anonymize(db: Session, ctx: RequestContext, user: User) -> dict:
    """Irreversibly scrub the person's PII. RETAINS de-identified rows (FK integrity).
    Returns a NON-PII summary of what was anonymized vs retained."""
    tid = uuid.UUID(str(ctx.tenant_id))
    email = user.email
    cands = db.execute(
        select(Candidate)
        .options(undefer(Candidate.phone_enc), undefer(Candidate.pan_enc))
        .where(Candidate.tenant_id == tid, Candidate.email == email)
    ).scalars().all()

    resume_keys, apps_retained = [], 0
    for c in cands:
        if c.resume_s3_key:
            resume_keys.append(c.resume_s3_key)
        apps_retained += db.execute(
            select(func.count()).select_from(Application)
            .where(Application.candidate_id == c.id)
        ).scalar_one()
        # scrub PII; keep the row de-identified
        c.full_name = ERASED            # NOT NULL → tombstone, not null
        c.email = None
        c.phone_enc = None
        c.pan_enc = None
        c.phone_bidx = None             # CRITICAL: clear the pseudonymous identifiers
        c.pan_bidx = None
        c.search_doc = None
        c.source = None
        c.resume_s3_key = None
        if c.deleted_at is None:
            c.deleted_at = _now()

    resume_deleted = _delete_resume_objects(resume_keys)

    # disable + anonymize the login (NOT hard-delete — preserve FK refs). email LAST
    # (it was the candidate match key above). Tombstone keeps NOT NULL + UNIQUE.
    user.full_name = ERASED
    user.password_hash = "!erased"      # unusable hash → login impossible
    user.status = "erased"
    user.email = f"erased-{user.id}@erased.invalid"

    return {
        "candidates_anonymized": len(cands),
        "blind_indexes_cleared": True,
        "applications_retained_deidentified": apps_retained,
        "resume_objects_deleted": resume_deleted,
        "user_disabled": True,
        "retained_untouched": ["consents", "audit_logs", "dpdp_requests"],
    }


def run_erasure(db: Session, ctx: RequestContext, request: DpdpRequest, user: User) -> dict:
    """Process an APPROVED erasure: anonymize → audit (append-only) → completed.
    The `approved` gate is asserted here — anonymization NEVER runs otherwise."""
    if request.status != APPROVED:
        raise ValueError(f"erasure requires an approved transition (got '{request.status}')")
    request.status = PROCESSING
    db.flush()
    summary = _anonymize(db, ctx, user)
    # append-only disclosure of what was erased vs retained (who/when via write_audit)
    write_audit(db, ctx, "dpdp.erasure_executed", "dpdp_request", request.id, after=summary)
    request.status = COMPLETED
    request.completed_at = _now()
    request.detail = {**(request.detail or {}), "summary": summary}
    # NOTE: auto-purge intentionally NOT invoked — see auto_purge_due_requests (stub).
    return summary


def auto_purge_due_requests(db: Session) -> int:
    """STUB — DO NOT IMPLEMENT a timed hard-delete here.

    Auto-purge of anonymized records after the statutory retention period is BLOCKED
    pending legally-confirmed retention numbers (GST/TDS/DPDP) — `settings.dpdp_retention_days`
    is deliberately None. This is a no-op that deletes NOTHING. Activating it requires
    legal input (PENDING B1) and an explicit, reviewed implementation.
    """
    if settings.dpdp_retention_days is None:
        log.warning("auto-purge pending legal retention-period determination — not configured; "
                    "purging NOTHING")
        return 0
    # Even when a period is set, Stage 1 performs NO deletion — guard against premature purge.
    log.warning("auto-purge is a Stage-1 stub — deletion deliberately not implemented; purging NOTHING")
    return 0
