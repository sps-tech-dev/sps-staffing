"""One-off F3a real-op verification on dev RDS — sps_app.

Legs: explicit link on real RDS → my_applications returns live-stage rows →
candidate_overview real counts → the BOTH-DIFFERENT merge case flags durably
(audit row + timeline event + loser retains user_id) → unlinked user → zeros
not error. Self-cleans business rows; timeline rows left for master cleanup.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import User
from app.models_staffing import Application, Candidate, CandidateDupReview, Job
from app.readmodels import candidate_overview, my_applications

TAG = "[F3a probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    fake_u1, fake_u2 = uuid.uuid4(), uuid.uuid4()   # soft ref — no FK, safe to synthesize
    try:
        cand = Candidate(tenant_id=tid, full_name=f"Probe Link Cand {TAG}", user_id=fake_u1)
        db.add(cand); db.flush()
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Link Job {TAG}")
        db.add(job); db.flush()
        db.add(Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, stage="client_round_2"))
        db.commit()

        ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                             user_id=str(fake_u1), roles=("candidate",))
        apps = my_applications(db, ctx)
        assert len(apps) == 1 and apps[0]["stage"] == "client_round_2"
        ov = candidate_overview(db, ctx)
        assert ov["applications"] == 1 and ov["recent"][0]["stage"] == "client_round_2"
        print("1. linked user on real RDS: /me/applications live stage + real overview counts ✅")

        ctx_bare = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                                  user_id=str(uuid.uuid4()), roles=("candidate",))
        assert my_applications(db, ctx_bare) == []
        assert candidate_overview(db, ctx_bare)["applications"] == 0
        print("2. unlinked user: [] + zeros, gracefully — not an error ✅")

        # BOTH-DIFFERENT merge on real RDS (the provably-correct case)
        surv = Candidate(tenant_id=tid, full_name=f"Probe Merge Surv {TAG}", user_id=fake_u1)
        loser = Candidate(tenant_id=tid, full_name=f"Probe Merge Loser {TAG}", user_id=fake_u2)
        db.add_all([surv, loser]); db.flush()
        review = CandidateDupReview(tenant_id=tid, business_unit_id="STAFFING",
                                    candidate_id=loser.id, matched_candidate_id=surv.id,
                                    match_type="fuzzy", score=0.9, status="pending")
        db.add(review); db.commit()
        from app.routers.dup_reviews import merge_dup_review
        staff_ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                                   user_id=None, roles=("recruiter",))
        merge_dup_review(review_id=review.id, ctx=staff_ctx, db=db, idempotency_key=None)
        db.refresh(surv); db.refresh(loser)
        assert surv.user_id == fake_u1                     # survivor keeps ITS login
        assert loser.user_id == fake_u2                    # loser RETAINS its user_id
        assert loser.deleted_at is not None
        n_flag = db.execute(text(
            "SELECT count(*) FROM shared.audit_logs WHERE tenant_id=:t "
            "AND action='candidate.merge_link_conflict' AND after->>'loser_user_id'=:l"),
            {"t": str(tid), "l": str(fake_u2)}).scalar_one()
        n_tl = db.execute(text(
            "SELECT count(*) FROM staffing.candidate_timeline WHERE tenant_id=:t "
            "AND event_type='MergeLinkConflict'"), {"t": str(tid)}).scalar_one()
        assert n_flag == 1 and n_tl >= 1
        print("3. BOTH-DIFFERENT merge on real RDS: survivor keeps login, loser retains "
              "user_id, conflict audit row + timeline event written — no data loss ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(CandidateDupReview).where(CandidateDupReview.tenant_id == tid,
                   CandidateDupReview.candidate_id.in_(select(Candidate.id).where(
                       Candidate.full_name.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("4. probe business rows cleaned (timeline rows → master cleanup)")
    print("F3a REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
