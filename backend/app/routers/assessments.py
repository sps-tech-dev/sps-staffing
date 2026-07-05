"""Aptitude test engine — STAFF surface (B.7): issue a one-time test link + the
tests dashboard. The candidate-facing surface is app/routers/take.py (token-gated).

Issue-time precondition: the application must be AT stage 'aptitude_test' (the
submit path drives aptitude_test → aptitude_passed|failed through the B.5 guard;
issuing at any other stage would create a test whose result can't land).
Retake (B.7 owns it): after a FAILED submitted attempt, re-issue is allowed only
after TEST_RETAKE_COOLDOWN_DAYS; attempt_no increments; a FRESH paper is frozen.
Only one live (issued/started, unexpired) test per application at a time.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel, field_validator
from sqlalchemy.orm.attributes import flag_modified

from .. import assessment_engine as engine
from .. import pipeline
from ..audit import write_audit
from ..config import settings
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..features import is_enabled
from ..idempotency import get_cached, store
from ..models_staffing import Application, Question, QuestionBank, Test
from ..timeline import EventType, emit_timeline
from .admin import _require_admin
from .staffing import BU, _require_staff, _tid

router = APIRouter()


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _err(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def select_bank_paper(db, tenant_id, business_unit_id: str, count: int) -> list[dict]:
    """A4 engine seam (the ONLY generic extension): draw `count` active questions
    from the ACTIVE bank(s) of a SPECIFIC business unit, then freeze. Threads the
    BU + count through — freeze_paper/select_questions signatures are untouched.
    The BU filter also ISOLATES verticals (academy questions never leak into a
    staffing paper and vice-versa)."""
    questions = db.execute(
        select(Question)
        .join(QuestionBank, QuestionBank.id == Question.bank_id)
        .where(Question.tenant_id == tenant_id, Question.is_active.is_(True),
               Question.deleted_at.is_(None), QuestionBank.is_active.is_(True),
               QuestionBank.deleted_at.is_(None),
               QuestionBank.business_unit_id == business_unit_id)).scalars().all()
    if not questions:
        raise _err(409, "NO_QUESTIONS", "No active question bank for this business unit")
    return engine.freeze_paper(engine.select_questions(questions, count))


@router.post("/applications/{app_id}/tests/issue")
def issue_test(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db),
               idempotency_key: str | None = Header(default=None)):
    """Freeze a paper + mint the ONE-TIME candidate link. The raw token appears in
    this response only; the DB stores its SHA-256."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    appn = db.execute(select(Application).where(
        Application.id == app_id, Application.tenant_id == _tid(ctx),
        Application.business_unit_id == BU,
        Application.deleted_at.is_(None))).scalar_one_or_none()
    if appn is None:
        raise _err(404, "NOT_FOUND", "Application not found")
    if appn.stage != "aptitude_test":
        raise _err(409, "STAGE_INVALID",
                   "Application must be at 'aptitude_test' to issue a test")

    prior = db.execute(select(Test).where(Test.application_id == appn.id,
                                          Test.deleted_at.is_(None))
                       .order_by(Test.attempt_no.desc())).scalars().all()
    now = _now()
    for t in prior:
        if t.status in ("issued", "started") and t.valid_until > now:
            raise _err(409, "TEST_ACTIVE", "An active test link already exists for this application")
    last_submitted = next((t for t in prior if t.status == "submitted"), None)
    if last_submitted is not None and last_submitted.passed is False:
        cooldown_ends = last_submitted.submitted_at + dt.timedelta(
            days=settings.test_retake_cooldown_days)
        if now < cooldown_ends:
            raise _err(409, "RETAKE_COOLDOWN",
                       f"Retake allowed after {cooldown_ends.date().isoformat()}")

    frozen = select_bank_paper(db, _tid(ctx), BU, settings.test_question_count)
    raw_token, token_hash = engine.new_link_token()
    test = Test(tenant_id=_tid(ctx), business_unit_id=BU, application_id=appn.id,
                candidate_id=appn.candidate_id, link_token_hash=token_hash,
                valid_until=now + dt.timedelta(hours=settings.test_link_ttl_hours),
                attempt_no=(max((t.attempt_no for t in prior), default=0) + 1),
                served_questions=frozen)
    db.add(test)
    db.flush()
    write_audit(db, ctx, "test.issue", "test", test.id,
                after={"application_id": str(appn.id), "attempt_no": test.attempt_no,
                       "question_count": len(frozen)})
    # NOTE: the assessment-invite EMAIL is B.10/SES — until then staff share the
    # link out-of-band; the intended send is logged via this audit row.
    db.commit()
    res = {"test_id": str(test.id), "take_path": f"/api/take/{raw_token}",
           "valid_until": test.valid_until.isoformat(), "attempt_no": test.attempt_no,
           "question_count": len(frozen),
           "time_limit_minutes": settings.test_time_limit_minutes}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


class WaiveIn(BaseModel):
    result: str
    reason: str

    @field_validator("result")
    @classmethod
    def _r(cls, v):
        if v not in ("pass", "fail"):
            raise ValueError("result must be 'pass' or 'fail'")
        return v

    @field_validator("reason")
    @classmethod
    def _re(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("A reason is required to waive an assessment")
        return v


@router.post("/applications/{app_id}/tests/{test_id}/waive")
def waive_test(app_id: uuid.UUID, test_id: uuid.UUID, body: WaiveIn,
               ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db),
               idempotency_key: str | None = Header(default=None)):
    """ADMIN assessment waiver (B.7, FEATURE_ASSESSMENT_WAIVER — a governed
    per-tenant capability, OFF by default → 404, probe-proof). Marks an ISSUED/
    STARTED test as decided without grading: passed set, score stays NULL (a
    waived pass is NEVER indistinguishable from a graded one), waived block in
    proctor_flags, transition through the guard, ONE TestCompletion
    {source:'admin_waive'} — the THIRD emitter. A graded test cannot be waived;
    a waived test cannot then be taken (mutual exclusion, both directions)."""
    if not is_enabled("assessment_waiver", ctx):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
    _require_admin(ctx)   # stricter than staff — recruiters cannot waive
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    t = db.execute(select(Test).where(Test.id == test_id, Test.application_id == app_id,
                                      Test.tenant_id == _tid(ctx),
                                      Test.deleted_at.is_(None))).scalar_one_or_none()
    if t is None:
        raise _err(404, "NOT_FOUND", "Test not found")

    waived_block = (t.proctor_flags or {}).get("waived")
    if waived_block is not None:      # idempotent re-waive → stored result, no dup
        res = {"test_id": str(t.id), "passed": t.passed, "waived": True,
               "already_waived": True}
        store(str(ctx.tenant_id), idempotency_key, res)
        return res
    if t.status == "submitted":
        raise _err(409, "ALREADY_GRADED", "A graded test result cannot be waived")

    appn = db.get(Application, t.application_id)
    if appn is None or appn.deleted_at is not None or appn.stage != "aptitude_test":
        raise _err(409, "STAGE_INVALID",
                   "Application must be at 'aptitude_test' to waive its test")

    passed = body.result == "pass"
    now = _now()
    t.status = "submitted"            # closed — the take surface refuses it (waived block)
    t.passed = passed
    t.score = None                    # NEVER a fake number: score=NULL + waived=true is the tell
    t.submitted_at = now              # waived FAIL follows the same retake cooldown
    flags = t.proctor_flags or {}
    flags["waived"] = {"by": str(ctx.user_id) if ctx.user_id else None,
                       "reason": body.reason, "at": now.isoformat(),
                       "source": "admin_waive"}
    t.proctor_flags = flags
    flag_modified(t, "proctor_flags")

    pipeline.transition(db, appn, "aptitude_passed" if passed else "aptitude_failed",
                        ctx=ctx, expected_version=appn.version)
    emit_timeline(db, candidate_id=t.candidate_id, event_type=EventType.TEST_COMPLETION,
                  payload={"application_id": str(appn.id), "round": 1, "result": body.result,
                           "source": "admin_waive"}, ctx=ctx)
    write_audit(db, ctx, "test.waive", "test", t.id,
                after={"application_id": str(appn.id), "result": body.result,
                       "reason": body.reason})
    db.commit()
    res = {"test_id": str(t.id), "passed": passed, "waived": True,
           "stage": "aptitude_passed" if passed else "aptitude_failed"}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/tests")
def list_tests(application_id: uuid.UUID | None = Query(default=None),
               ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db)):
    """Staff dashboard: attempts + status/score. NEVER returns served_questions
    (the frozen paper holds correct answers) nor the token hash."""
    _require_staff(ctx)
    stmt = select(Test).where(Test.tenant_id == _tid(ctx), Test.deleted_at.is_(None))
    if application_id:
        stmt = stmt.where(Test.application_id == application_id)
    rows = db.execute(stmt.order_by(Test.created_at.desc()).limit(100)).scalars().all()
    now = _now()
    return [{"id": str(t.id), "application_id": str(t.application_id),
             "status": ("expired" if t.status in ("issued", "started") and t.valid_until < now
                        else t.status),
             "attempt_no": t.attempt_no,
             "score": float(t.score) if t.score is not None else None,
             "passed": t.passed,
             # a waived pass must NEVER look like a graded pass: score=NULL + waived=true
             "waived": (t.proctor_flags or {}).get("waived") is not None,
             "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
             "snapshots": len((t.proctor_flags or {}).get("snapshots", []))} for t in rows]
