"""One-off B.6 real-op verification on dev RDS — runs on the BACKEND task def (sps_app).

Proves on real RDS: internal_evaluations table + endpoint logic under sps_app,
R1 pass → aptitude_passed + TestCompletion, the no-shortcut invariant, R2 pass,
RTR, submit. Probe rows tagged '[B.6 probe]'; business rows self-cleaned;
timeline rows left for the master cleanup task. Exits non-zero on any failure.
"""
from __future__ import annotations

import sys

from sqlalchemy import delete, select, text

from app import pipeline
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import Consent
from app.models_staffing import Application, Candidate, InternalEvaluation, Job

TAG = "[B.6 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None,
                         roles=("recruiter",))
    ok = False
    try:
        cand = Candidate(tenant_id=tid, full_name=f"Probe Eval Cand {TAG}")
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Eval Job {TAG}")
        db.add_all([cand, job]); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, stage="applied")
        db.add(appn); db.commit()

        v = pipeline.transition(db, appn, "screening", ctx=ctx, expected_version=1)["version"]
        db.commit()
        v = pipeline.transition(db, appn, "aptitude_test", ctx=ctx, expected_version=v)["version"]
        db.commit()

        try:  # invariant: no shortcut
            pipeline.transition(db, appn, "submitted_to_client", ctx=ctx, expected_version=v)
            print("shortcut allowed ❌"); return 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            assert "ILLEGAL_TRANSITION" in str(getattr(e, "detail", e))
        print("1. no-shortcut invariant holds on real RDS ✅")

        # R1 pass (evaluation row + transition + TestCompletion, one txn)
        db.add(InternalEvaluation(tenant_id=tid, business_unit_id="STAFFING",
                                  application_id=appn.id, round=1, result="pass",
                                  notes="B.6 probe"))
        v = pipeline.transition(db, appn, "aptitude_passed", ctx=ctx, expected_version=v)["version"]
        from app.timeline import EventType, emit_timeline
        emit_timeline(db, candidate_id=cand.id, event_type=EventType.TEST_COMPLETION,
                      payload={"application_id": str(appn.id), "round": 1, "result": "pass"}, ctx=ctx)
        db.commit()
        n_tc = db.execute(text("SELECT count(*) FROM staffing.candidate_timeline "
                               "WHERE candidate_id=:c AND event_type='TestCompletion'"),
                          {"c": str(cand.id)}).scalar_one()
        assert n_tc == 1
        print("2. R1 pass → aptitude_passed + TestCompletion row on real RDS ✅")

        v = pipeline.transition(db, appn, "internal_interview", ctx=ctx, expected_version=v)["version"]
        db.commit()
        db.add(InternalEvaluation(tenant_id=tid, business_unit_id="STAFFING",
                                  application_id=appn.id, round=2, result="pass"))
        v = pipeline.transition(db, appn, "internal_passed", ctx=ctx, expected_version=v)["version"]
        db.commit()
        v = pipeline.transition(db, appn, "rtr_pending", ctx=ctx, expected_version=v)["version"]
        db.commit()
        import datetime as dt
        appn.rtr_consent_at = dt.datetime.now(dt.timezone.utc)
        db.add(Consent(tenant_id=tid, subject_candidate_id=cand.id, purpose="rtr",
                       granted=True, policy_version="rtr-v1"))
        db.commit()
        v = pipeline.transition(db, appn, "submitted_to_client", ctx=ctx, expected_version=v)["version"]
        db.commit()
        db.refresh(appn)
        assert appn.stage == "submitted_to_client"
        n_ev = db.execute(text("SELECT count(*) FROM staffing.internal_evaluations "
                               "WHERE application_id=:a"), {"a": str(appn.id)}).scalar_one()
        assert n_ev == 2
        print(f"3. R2 pass → RTR → submitted_to_client on real RDS (2 evaluation rows) ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(InternalEvaluation).where(InternalEvaluation.tenant_id == tid,
                   InternalEvaluation.application_id.in_(
                       select(Application.id).join(Job, Job.id == Application.job_id)
                       .where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("4. probe business rows cleaned (timeline + consent rows left for master cleanup)")
    print("B.6 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
