"""One-off B.5-fix verification on dev RDS — sps_app. The two endpoints that
500'd since B.5 must now work against real data: seed apps across new-vocabulary
stages → job_pipeline returns all 21 buckets with rows placed correctly →
employer_overview returns CORRECT NON-ZERO counts (not silent zeros). Self-cleans
business rows; timeline untouched (direct ORM seeding)."""
from __future__ import annotations

import sys

from sqlalchemy import delete, select, text

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import APPLICATION_STAGES, Application, Candidate, Client, Job
from app.routers.staffing import employer_overview, job_pipeline

TAG = "[B.5-fix probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                         user_id=None, roles=("recruiter",))
    ok = False
    try:
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Fix Job {TAG}")
        db.add(job); db.flush()
        for i, stage in enumerate(("screening", "client_round_1", "joined")):
            cand = Candidate(tenant_id=tid, full_name=f"Probe Fix Cand {i} {TAG}")
            db.add(cand); db.flush()
            db.add(Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                               candidate_id=cand.id, stage=stage))
        db.commit()

        pipe = job_pipeline(job_id=job.id, ctx=ctx, db=db)
        assert set(pipe["stages"].keys()) == set(APPLICATION_STAGES)
        assert len(pipe["stages"]["screening"]) == 1
        assert len(pipe["stages"]["joined"]) == 1
        print(f"1. job_pipeline on dev RDS: 21 buckets, rows placed correctly "
              f"(was 500 since B.5) ✅")

        ov = employer_overview(ctx=ctx, db=db)
        funnel = {f["label"]: f["value"] for f in ov["funnel"]}
        assert ov["interviews"] >= 1              # client_round_1 counts
        assert ov["placements"] >= 1              # joined counts
        assert funnel["Screening"] >= 1 and funnel["Client Rounds"] >= 1 \
            and funnel["Joined"] >= 1
        print(f"2. employer_overview on dev RDS: NON-ZERO new-vocabulary counts "
              f"(interviews={ov['interviews']}, placements={ov['placements']}, "
              f"funnel hits={[k for k, v in funnel.items() if v]}) — was 500 + dead "
              f"vocabulary ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("3. probe rows cleaned up")
    print("B.5-FIX REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
