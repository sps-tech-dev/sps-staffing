"""Candidate timeline emitter (B.2, Part 18) — append-only, INSERT-only.

emit_timeline() adds a staffing.candidate_timeline row INSIDE the caller's
transaction (the caller commits), exactly like write_audit(): the row lands
atomically with the state change it describes, and the endpoint's
Idempotency-Key guard therefore covers it — a replayed mutation returns the
cached result before reaching the emit, so it never double-appends.

Append-only is DB-enforced: sps_app has no UPDATE/DELETE on the table
(bootstrap_app_role.py REVOKE). There is no update/delete helper here on purpose.

Payloads must stay NON-PII: ids, stages, keys, timestamps — never names, emails,
phone numbers or resume text.
"""
from __future__ import annotations

import uuid

from .context import RequestContext
from .models_staffing import CandidateTimeline


class EventType:
    """Canonical candidate timeline event types (Part 18).

    All constants are defined up front; only events with a REAL source today are
    emitted anywhere. The rest are wired when their feature lands:
      - TEST_COMPLETION       → B.7 assessment engine
      - JOINING               → B.9 placements
      - GUARANTEE_COMPLETION  → B.9 guarantee clock
      - PROFILE_UPDATE        → no candidate-update endpoint exists yet
    """
    REGISTRATION = "Registration"
    RESUME_UPLOAD = "ResumeUpload"
    PROFILE_UPDATE = "ProfileUpdate"          # no emit site yet (no update endpoint)
    APPLICATION = "Application"
    STAGE_CHANGE = "StageChange"              # from/to in payload
    TEST_COMPLETION = "TestCompletion"        # TODO(B.7): emit from the assessment engine
    INTERVIEW = "Interview"
    SUBMISSION = "Submission"
    OFFER = "Offer"
    JOINING = "Joining"                       # TODO(B.9): emit from placements
    GUARANTEE_COMPLETION = "GuaranteeCompletion"  # TODO(B.9): emit from the guarantee clock
    # B.3 merge events (added beyond the original Part-18 list, ratified at STOP-1):
    MERGED = "Merged"                         # on the SURVIVOR: merged candidate X in
    MERGED_INTO = "MergedInto"                # on the LOSER (before soft-delete): merged into Y
    MERGE_LINK_CONFLICT = "MergeLinkConflict"  # both merge sides had DIFFERENT portal logins (F3a)

    ALL = frozenset({
        REGISTRATION, RESUME_UPLOAD, PROFILE_UPDATE, APPLICATION, STAGE_CHANGE,
        TEST_COMPLETION, INTERVIEW, SUBMISSION, OFFER, JOINING, GUARANTEE_COMPLETION,
        MERGED, MERGED_INTO, MERGE_LINK_CONFLICT,
    })


def emit_timeline(db, *, candidate_id: uuid.UUID | str, event_type: str,
                  payload: dict | None = None, actor_id: uuid.UUID | str | None = None,
                  ctx: RequestContext) -> None:
    """Append one timeline event inside the caller's transaction. INSERT-only."""
    assert event_type in EventType.ALL, f"unknown timeline event_type: {event_type}"
    db.add(CandidateTimeline(
        tenant_id=uuid.UUID(str(ctx.tenant_id)),
        business_unit_id=ctx.business_unit_id or "STAFFING",
        candidate_id=uuid.UUID(str(candidate_id)),
        event_type=event_type,
        payload=payload or {},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else (
            uuid.UUID(str(ctx.user_id)) if ctx.user_id else None),
    ))
