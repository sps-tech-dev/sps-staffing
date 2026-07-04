"""One-off B.3 real-op verification on dev RDS — runs on the BACKEND task def (sps_app).

Proves what local/moto can't: pg_trgm + public.similarity() resolution on REAL RDS
under the app role, the fuzzy flag write, and a full merge (repoint + retire +
timeline events) executed as sps_app.

Flow: two fuzzy-similar probe candidates (skills overlap) → flag_if_fuzzy_dup finds
the match (pending review) → a probe job+application on the loser → merge via the
real endpoint function → assert repoint/soft-delete/bidx-null/events. Probe rows are
tagged '[B.3 probe]'; candidate/job/application/review rows are cleaned here (sps_app
has DML), timeline rows CANNOT be deleted by sps_app (append-only, by design) — they
are removed afterwards by the master cleanup task. Exits non-zero on any failure.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app import dedup
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import Application, Candidate, CandidateDupReview, Job
from app.routers.dup_reviews import merge_dup_review

TAG = "[B.3 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    try:
        sim = db.execute(text("SELECT public.similarity('probe','probe')")).scalar_one()
        assert sim == 1.0
        print("1. public.similarity() resolves as sps_app on real RDS ✅")

        surv = Candidate(tenant_id=tid, full_name=f"Probe Merge Target {TAG}", skills=["b3probe"])
        db.add(surv); db.flush()
        loser = Candidate(tenant_id=tid, full_name=f"Probe Merge Targett {TAG}", skills=["B3Probe"])
        db.add(loser); db.flush()
        dedup.flag_if_fuzzy_dup(db, tenant_id=tid, candidate=loser,
                                skills=["B3Probe"], source="b3_probe")
        db.commit()
        rv = db.execute(select(CandidateDupReview).where(
            CandidateDupReview.tenant_id == tid,
            CandidateDupReview.candidate_id == loser.id,
            CandidateDupReview.status == "pending")).scalar_one()
        assert rv.matched_candidate_id == surv.id and float(rv.score) >= 0.4
        print(f"2. fuzzy flag on real RDS ✅ (review id={rv.id}, score={float(rv.score):.2f})")

        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Job {TAG}")
        db.add(job); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=loser.id, stage="applied")
        db.add(appn); db.commit()

        ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None,
                             roles=("recruiter",))
        res = merge_dup_review(review_id=rv.id, ctx=ctx, db=db, idempotency_key=None)
        assert res["status"] == "merged"
        db.expire_all()
        assert db.get(Application, appn.id).candidate_id == surv.id
        lr = db.get(Candidate, loser.id)
        assert lr.deleted_at is not None and lr.phone_bidx is None and lr.pan_bidx is None
        n_events = db.execute(text(
            "SELECT count(*) FROM staffing.candidate_timeline "
            "WHERE event_type IN ('Merged','MergedInto') AND candidate_id IN (:a,:b)"),
            {"a": str(surv.id), "b": str(loser.id)}).scalar_one()
        assert n_events == 2
        print("3. merge as sps_app ✅ — application repointed, loser retired "
              "(soft-deleted, bidx nulled), Merged+MergedInto emitted")
        ok = True
    finally:
        # sps_app can clean everything EXCEPT timeline rows (append-only) — master task follows.
        db.execute(delete(CandidateDupReview).where(CandidateDupReview.tenant_id == tid,
                   CandidateDupReview.incoming_payload["source"].astext == "b3_probe"))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit()
        print("4. probe business rows cleaned (timeline rows left for master cleanup)")
        db.close()
    print("B.3 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
