"""Aptitude test — CANDIDATE surface (B.7). Token-gated: NO JWT, no cookies, no
staff code paths. The one-time token (SHA-256-matched against tests.link_token_hash)
is the ENTIRE authority: it resolves to exactly one test row, and tenant/candidate/
application context derives from that row only — client input is never trusted for
scoping. A staff JWT is useless here; a token can never reach another test.

Error discipline (anti-enumeration): unknown token → 404; expired or already
submitted → 410. Same body shape; no signal beyond the necessary split.

What the token can do: fetch the frozen paper ONCE-started (stems + shuffled
options — NEVER the correct answers), submit answers once (idempotent replay
returns the stored result), and presign proctoring snapshot PUTs while started.
Nothing else.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import assessment_engine as engine
from .. import pipeline, storage
from ..config import settings
from ..context import RequestContext
from ..db import get_db
from ..models_staffing import Application, Test
from ..timeline import EventType, emit_timeline

router = APIRouter()


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _gone():
    return HTTPException(status_code=410, detail={"code": "GONE", "message": "This test link is no longer valid"})


def _not_found():
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Unknown test link"})


def _resolve(db: Session, token: str) -> Test:
    """Token → test row by hash. 404 unknown; expiry/status handled by callers."""
    t = db.execute(select(Test).where(
        Test.link_token_hash == engine.hash_token(token),
        Test.deleted_at.is_(None))).scalar_one_or_none()
    if t is None:
        raise _not_found()
    return t


@router.get("/{token}")
def fetch_paper(token: str, db: Session = Depends(get_db)):
    """First fetch marks the test STARTED (single-use start). Returns the frozen
    stems + shuffled options ONLY — correct answers never leave the server."""
    t = _resolve(db, token)
    if t.status == "submitted" or t.valid_until < _now():
        raise _gone()
    if t.status == "issued":
        t.status = "started"
        t.started_at = _now()
        db.commit()
    return {"questions": engine.public_paper(t.served_questions or []),
            "attempt_no": t.attempt_no,
            "time_limit_minutes": settings.test_time_limit_minutes,
            "expires_at": t.valid_until.isoformat()}


class SubmitIn(BaseModel):
    answers: dict[str, int]


@router.post("/{token}/submit")
def submit_answers(token: str, body: SubmitIn, db: Session = Depends(get_db)):
    """Auto-grade against the FROZEN paper (never a bank re-query). Drives
    aptitude_test → aptitude_passed|failed through the B.5 guard as the AUTOMATED
    second emitter of TestCompletion (B.6's manual endpoint remains the override —
    if staff already advanced the stage, the grade is stored and the pipeline is
    left untouched: no double transition, no double event). Idempotent: a second
    submit returns the stored result."""
    t = _resolve(db, token)
    if t.status == "submitted":
        if (t.proctor_flags or {}).get("waived") is not None:
            raise _gone()   # mutual exclusion: a waived test is closed to the take surface
        return {"score": float(t.score), "passed": t.passed, "already_submitted": True}
    if t.valid_until < _now():
        raise _gone()

    score, passed, _per_q = engine.grade(t.served_questions or [], body.answers)
    t.score = score
    t.passed = passed
    t.status = "submitted"
    t.submitted_at = _now()

    appn = db.get(Application, t.application_id)
    ctx = RequestContext(tenant_id=str(t.tenant_id), business_unit_id="STAFFING",
                         user_id=None, roles=())
    pipeline_advanced = False
    if appn is not None and appn.deleted_at is None and appn.stage == "aptitude_test":
        target = "aptitude_passed" if passed else "aptitude_failed"
        pipeline.transition(db, appn, target, ctx=ctx, expected_version=appn.version)
        emit_timeline(db, candidate_id=t.candidate_id, event_type=EventType.TEST_COMPLETION,
                      payload={"application_id": str(t.application_id), "round": 1,
                               "result": "pass" if passed else "fail",
                               "score": round(score, 4), "source": "engine"}, ctx=ctx)
        pipeline_advanced = True
    db.commit()
    # NOTE: the "result within 30 min" EMAIL is B.10/SES — result surfaces in-app.
    return {"score": round(score, 4), "passed": passed,
            "pipeline_advanced": pipeline_advanced,
            "pass_threshold": settings.test_pass_threshold}


class SnapshotIn(BaseModel):
    content_type: str = "image/jpeg"


@router.post("/{token}/snapshot/presign")
def presign_snapshot(token: str, body: SnapshotIn, db: Session = Depends(get_db)):
    """Proctoring snapshot upload (B.7 provides storage only — the browser capture
    loop is the take-test FRONTEND, deferred). Short-lived presigned PUT under the
    candidate's canonical prefix; the key is recorded in proctor_flags."""
    t = _resolve(db, token)
    if t.status != "started" or t.valid_until < _now():
        raise _gone()
    if body.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=422, detail={
            "code": "UNSUPPORTED_TYPE", "message": "Snapshots must be JPEG or PNG"})
    flags = t.proctor_flags or {}
    snaps = flags.get("snapshots", [])
    if len(snaps) >= settings.test_max_snapshots:
        raise HTTPException(status_code=429, detail={
            "code": "SNAPSHOT_LIMIT", "message": "Snapshot limit reached"})
    ext = "jpg" if body.content_type == "image/jpeg" else "png"
    key = (f"tenant={t.tenant_id}/business_unit=STAFFING/candidates/{t.candidate_id}/"
           f"proctor/{t.id}/{uuid.uuid4()}.{ext}")
    url = storage.presign_put(key, body.content_type)
    snaps.append(key)
    flags["snapshots"] = snaps
    t.proctor_flags = flags
    flag_modified(t, "proctor_flags")
    db.commit()
    return {"upload_url": url, "key": key, "expires_in": storage.PRESIGN_PUT_TTL}
