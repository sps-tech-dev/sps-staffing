"""One-off B.5 real-op verification on dev RDS — runs on the BACKEND task def (sps_app).

Proves on REAL RDS what local can't: the new stage CHECK, the optimistic-lock CAS
under the app role, the RTR gate, and StageChange timeline emission. Also verifies
the post-migration vocabulary (no old-vocabulary stage values remain).

Probe rows tagged '[B.5 probe]'; business rows self-cleaned; timeline rows left
for the master cleanup task (append-only). Exits non-zero on any failure.
"""
from __future__ import annotations

import sys

from sqlalchemy import delete, select, text

from app import pipeline
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import Application, Candidate, CandidateTimeline, Job

TAG = "[B.5 probe]"
OLD = ("sourced", "screened", "assessed", "submitted", "interview", "placed", "rejected")


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    try:
        stale_rows = db.execute(text(
            "SELECT DISTINCT stage FROM staffing.applications WHERE stage = ANY(:old)"),
            {"old": list(OLD)}).scalars().all()
        assert not stale_rows, f"old-vocabulary rows remain: {stale_rows}"
        print("1. post-migration DISTINCT check: no old-vocabulary stages on dev RDS ✅")

        cand = Candidate(tenant_id=tid, full_name=f"Probe Pipe Cand {TAG}")
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Pipe Job {TAG}")
        db.add_all([cand, job]); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, stage="applied")
        db.add(appn); db.commit()
        assert appn.version == 1
        print("2. probe application created (stage=applied, version=1) ✅")

        ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None,
                             roles=("recruiter",))
        v = 1
        for st in ("screening", "aptitude_test", "aptitude_passed", "internal_interview",
                   "internal_passed", "rtr_pending"):
            res = pipeline.transition(db, appn, st, ctx=ctx, expected_version=v)
            db.commit(); v = res["version"]
        print(f"3. six legal transitions on real RDS (version={v}) ✅")

        try:
            pipeline.transition(db, appn, "submitted_to_client", ctx=ctx, expected_version=v)
            print("RTR gate FAILED to block ❌"); return 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            assert "RTR_REQUIRED" in str(getattr(e, "detail", e)), e
        print("4. RTR gate blocks submit on real RDS ✅")

        try:
            pipeline.transition(db, appn, "on_hold", ctx=ctx, expected_version=v - 1)
            print("stale CAS FAILED to block ❌"); return 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            assert "STALE_STATE" in str(getattr(e, "detail", e)), e
        print("5. optimistic lock (stale version) 409 on real RDS ✅")

        res = pipeline.transition(db, appn, "withdrawn", ctx=ctx, expected_version=v,
                                  reason="B.5 probe teardown")
        db.commit()
        assert res["stage"] == "withdrawn"
        n_tl = db.execute(text(
            "SELECT count(*) FROM staffing.candidate_timeline "
            "WHERE candidate_id = :c AND event_type = 'StageChange'"),
            {"c": str(cand.id)}).scalar_one()
        assert n_tl == 7, f"expected 7 StageChange rows, got {n_tl}"
        print("6. withdraw-with-reason + 7 StageChange timeline rows ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("7. probe business rows cleaned (timeline rows left for master cleanup)")
    print("B.5 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
