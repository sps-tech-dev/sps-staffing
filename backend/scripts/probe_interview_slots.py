"""One-off B.8 real-op verification on dev RDS — BACKEND task def (sps_app).

Probe: interview → propose 3 slots → choose (scheduled + Interview timeline row) →
.ics content (UID/SEQUENCE/DTSTART) → reschedule (SEQUENCE bump, slots wiped) →
no_show with reason. Self-cleans business rows; timeline rows for master cleanup.
"""
from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import delete, select, text

from app import ics as ics_mod
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Interview, InterviewSlot, Job,
)
from app.timeline import EventType, emit_timeline

TAG = "[B.8 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None, roles=())
    ok = False
    try:
        cand = Candidate(tenant_id=tid, full_name=f"Probe Slot Cand {TAG}")
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Slot Job {TAG}")
        db.add_all([cand, job]); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, stage="applied")
        db.add(appn); db.flush()
        iv = Interview(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                       mode="video", interviewer_name="Probe Panel", status="scheduled")
        db.add(iv); db.commit()

        base = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)
        slots = [InterviewSlot(tenant_id=tid, business_unit_id="STAFFING", interview_id=iv.id,
                               slot_start=base + dt.timedelta(days=k),
                               slot_end=base + dt.timedelta(days=k, hours=1))
                 for k in range(3)]
        db.add_all(slots); db.commit()
        n = db.execute(text("SELECT count(*) FROM staffing.interview_slots WHERE interview_id=:i"),
                       {"i": str(iv.id)}).scalar_one()
        assert n == 3
        print("1. interview_slots table live on dev RDS — 3 slots proposed ✅")

        chosen = slots[1]
        chosen.chosen = True
        iv.scheduled_at = chosen.slot_start
        emit_timeline(db, candidate_id=cand.id, event_type=EventType.INTERVIEW,
                      payload={"interview_id": str(iv.id), "action": "scheduled",
                               "scheduled_at": chosen.slot_start.isoformat()}, ctx=ctx)
        db.commit()
        content = ics_mod.build_ics(interview_id=iv.id, sequence=iv.ics_sequence,
                                    start=iv.scheduled_at, end=chosen.slot_end,
                                    candidate_name=cand.full_name, job_title=job.title,
                                    mode=iv.mode, interviewer_name=iv.interviewer_name)
        assert f"UID:interview-{iv.id}@" in content and "SEQUENCE:0" in content
        assert "DTSTART:" in content and "\r\n" in content
        print("2. choose → scheduled + valid .ics (UID/SEQUENCE:0/DTSTART/CRLF) ✅")

        iv.status = "rescheduled"
        iv.ics_sequence = iv.ics_sequence + 1
        db.execute(delete(InterviewSlot).where(InterviewSlot.interview_id == iv.id))
        db.commit(); db.refresh(iv)
        assert iv.ics_sequence == 1
        left = db.execute(text("SELECT count(*) FROM staffing.interview_slots "
                               "WHERE interview_id=:i"), {"i": str(iv.id)}).scalar_one()
        assert left == 0
        print("3. reschedule → SEQUENCE=1, slot round wiped ✅")

        iv.status = "no_show"
        iv.status_reason = "B.8 probe reason"
        db.commit(); db.refresh(iv)
        assert iv.status == "no_show" and iv.status_reason == "B.8 probe reason"
        n_tl = db.execute(text("SELECT count(*) FROM staffing.candidate_timeline "
                               "WHERE candidate_id=:c AND event_type='Interview'"),
                          {"c": str(cand.id)}).scalar_one()
        assert n_tl == 1
        print("4. no_show + reason persisted (widened CHECK live); Interview timeline row ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(InterviewSlot).where(InterviewSlot.tenant_id == tid,
                   InterviewSlot.interview_id.in_(select(Interview.id).join(
                       Application, Application.id == Interview.application_id)
                       .join(Job, Job.id == Application.job_id)
                       .where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Interview).where(Interview.tenant_id == tid,
                   Interview.application_id.in_(select(Application.id).join(
                       Job, Job.id == Application.job_id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("5. probe business rows cleaned (timeline rows left for master cleanup)")
    print("B.8 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
