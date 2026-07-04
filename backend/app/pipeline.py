"""Pipeline state machine (B.5) — THE ONLY module that writes applications.stage.

Two writers live here and nowhere else:
  - transition(): the guarded business transition (graph + gates + optimistic lock).
  - adopt_stage_on_merge(): the B.3 merge stage-adoption — a DOCUMENTED EXCEPTION
    that copies recorded state between two applications for the same job during a
    duplicate merge. It is not a business transition, so it does not walk the
    graph; it exists here so `grep 'stage =' app/` outside this module stays empty.

Guard rules (Part 5, STOP-1 approved):
  - Illegal src→dst → 409 ILLEGAL_TRANSITION.
  - withdrawn/dropped legal from ANY non-terminal stage, reason REQUIRED (422
    REASON_REQUIRED) → stored in drop_reason.
  - on_hold from any non-terminal stage; the prior stage is stored in
    hold_prior_stage; from on_hold the only legal targets are the stored prior
    stage (reopen), withdrawn, or dropped.
  - BEFORE submitted_to_client: (i) RTR consent must be recorded on the
    application (rtr_consent_at — set via POST /applications/{id}/rtr, which also
    appends the shared.consents 'rtr' ledger row) → else 409 RTR_REQUIRED.
    (ii) PII masking is STRUCTURAL: plaintext phone/pan columns were dropped in
    0008 and client-facing endpoints expose name-only cards (leak-tested); the
    guard asserts the structural invariant as a tripwire.
  - OPTIMISTIC LOCK: the stage write is a single conditional UPDATE
    (WHERE id AND tenant AND version = expected_version) that increments version;
    0 rows → 409 STALE_STATE. Concurrent movers cannot both win.
  - Every successful transition emits ONE StageChange timeline row and ONE audit
    row, inside the same transaction (caller commits).
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from .audit import write_audit
from .context import RequestContext
from .models_staffing import Application, Candidate
from .timeline import EventType, emit_timeline

# ── the Part-5 stage set ─────────────────────────────────────────
STAGES = (
    "applied", "screening", "aptitude_test", "aptitude_passed", "aptitude_failed",
    "internal_interview", "internal_passed", "rtr_pending", "submitted_to_client",
    "client_round_1", "client_round_2", "client_round_3", "offer", "offer_accepted",
    "joined", "guarantee", "invoiced", "paid", "withdrawn", "dropped", "on_hold",
)
TERMINAL = frozenset({"paid", "withdrawn", "dropped"})

# Forward graph (withdrawn/dropped/on_hold are handled as global rules, not edges).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "applied": {"screening"},
    "screening": {"aptitude_test"},
    "aptitude_test": {"aptitude_passed", "aptitude_failed"},
    "aptitude_passed": {"internal_interview"},
    "aptitude_failed": {"aptitude_test"},          # retake (cooldown = B.7)
    "internal_interview": {"internal_passed"},
    "internal_passed": {"rtr_pending"},
    "rtr_pending": {"submitted_to_client"},        # RTR gate asserted here
    "submitted_to_client": {"client_round_1"},
    "client_round_1": {"client_round_2", "offer"},
    "client_round_2": {"client_round_3", "offer"},
    "client_round_3": {"offer"},
    "offer": {"offer_accepted"},
    "offer_accepted": {"joined"},
    "joined": {"guarantee"},
    "guarantee": {"invoiced"},
    "invoiced": {"paid"},
    "paid": set(), "withdrawn": set(), "dropped": set(),
    "on_hold": set(),                              # special-cased: prior stage only
}

# Merge tie-break ranking (B.3 stage-adoption) — new vocabulary. Higher = further along.
STAGE_RANK = {
    "dropped": 0, "withdrawn": 0, "on_hold": 1,
    "applied": 2, "screening": 3, "aptitude_test": 4, "aptitude_failed": 4,
    "aptitude_passed": 5, "internal_interview": 6, "internal_passed": 7,
    "rtr_pending": 8, "submitted_to_client": 9,
    "client_round_1": 10, "client_round_2": 11, "client_round_3": 12,
    "offer": 13, "offer_accepted": 14, "joined": 15, "guarantee": 16,
    "invoiced": 17, "paid": 18,
}

# Recruiter SLA queue (employee overview): pre-offer, non-terminal, non-hold stages.
ACTIVE_STAGES = ["applied", "screening", "aptitude_test", "aptitude_passed",
                 "aptitude_failed", "internal_interview", "internal_passed",
                 "rtr_pending", "submitted_to_client",
                 "client_round_1", "client_round_2", "client_round_3"]


def _err(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def transition(db: Session, application: Application, to_stage: str, *,
               ctx: RequestContext, expected_version: int, reason: str | None = None) -> dict:
    """Perform one guarded stage transition. Caller commits. Returns the new state."""
    if to_stage not in STAGES:
        raise _err(422, "VALIDATION_ERROR", f"Unknown stage '{to_stage}'")
    src = application.stage

    if src in TERMINAL:
        raise _err(409, "ILLEGAL_TRANSITION", f"'{src}' is terminal")

    values: dict = {"stage": to_stage, "version": Application.version + 1}

    if to_stage in ("withdrawn", "dropped"):
        if not (reason and reason.strip()):
            raise _err(422, "REASON_REQUIRED", f"A reason is required to {to_stage.rstrip('n')}")
        values["drop_reason"] = reason.strip()
    elif to_stage == "on_hold":
        if src == "on_hold":
            raise _err(409, "ILLEGAL_TRANSITION", "Already on hold")
        values["hold_prior_stage"] = src
        values["hold_reason"] = (reason or "").strip() or None
    elif src == "on_hold":
        # reopen: ONLY back to the stored prior stage
        if application.hold_prior_stage is None:
            raise _err(409, "ILLEGAL_TRANSITION",
                       "No prior stage recorded (legacy hold) — withdraw/drop instead")
        if to_stage != application.hold_prior_stage:
            raise _err(409, "ILLEGAL_TRANSITION",
                       f"Reopen must return to '{application.hold_prior_stage}'")
        values["hold_prior_stage"] = None
        values["hold_reason"] = None
    else:
        if to_stage not in ALLOWED_TRANSITIONS.get(src, set()):
            raise _err(409, "ILLEGAL_TRANSITION", f"Cannot move {src} → {to_stage}")

    if to_stage == "submitted_to_client":
        if application.rtr_consent_at is None:
            raise _err(409, "RTR_REQUIRED",
                       "Right-to-Represent consent must be recorded before submitting to client")
        # PII-masking tripwire: plaintext phone/pan columns must not exist (dropped in 0008).
        assert not hasattr(Candidate, "phone") and not hasattr(Candidate, "pan"), \
            "plaintext PII columns reappeared — masking invariant broken"

    # optimistic lock: conditional UPDATE, version compare-and-increment
    res = db.execute(update(Application)
                     .where(Application.id == application.id,
                            Application.tenant_id == application.tenant_id,
                            Application.version == expected_version)
                     .values(**values))
    if (res.rowcount or 0) == 0:
        raise _err(409, "STALE_STATE",
                   "Application was modified concurrently — reload and retry")

    write_audit(db, ctx, "application.stage_change", "application", application.id,
                before={"stage": src, "version": expected_version},
                after={"stage": to_stage, "version": expected_version + 1,
                       **({"reason": reason} if reason else {})})
    emit_timeline(db, candidate_id=application.candidate_id, event_type=EventType.STAGE_CHANGE,
                  payload={"application_id": str(application.id), "from": src, "to": to_stage,
                           **({"reason": reason} if reason else {})}, ctx=ctx)
    db.expire(application)
    return {"id": str(application.id), "stage": to_stage, "version": expected_version + 1}


def adopt_stage_on_merge(survivor_app: Application, from_stage: str) -> None:
    """B.3 merge stage-adoption — documented exception (see module docstring).
    Copies the further-along recorded stage onto the survivor's application row
    during a duplicate merge. Not a business transition; audited by the merge."""
    survivor_app.stage = from_stage
