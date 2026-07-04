"""Employee/recruiter hub (Part 5 / Appendix D): requisition work-queue + SLA.

The queue is the recruiter's active applications (early pipeline stages) for the
tenant's STAFFING BU, oldest-first, each with an SLA status derived from time
since the last stage change. Authenticated, tenant + STAFFING scoped, staff-role.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..models_staffing import Application, Candidate, Job
from ..pipeline import ACTIVE_STAGES  # B.5: stage vocabulary owned by pipeline.py

router = APIRouter()
BU = "STAFFING"
SLA_TARGET_HOURS = 24          # act on a requisition within 24h (Part 5 / Appendix D)
SLA_WARN_HOURS = 18
STAFF_ROLES = {"owner", "super_admin", "admin", "business_manager", "manager",
               "recruiter", "coordinator", "employee"}


def _sla(age_hours: float) -> str:
    if age_hours >= SLA_TARGET_HOURS:
        return "breached"
    if age_hours >= SLA_WARN_HOURS:
        return "warning"
    return "ok"


@router.get("/overview")
def employee_overview(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    if ctx.client_id is not None or not (set(ctx.roles) & STAFF_ROLES):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Staff role required"})
    tid = uuid.UUID(str(ctx.tenant_id))
    now = dt.datetime.now(dt.timezone.utc)

    rows = db.execute(
        select(Application, Candidate, Job)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Application.tenant_id == tid, Application.business_unit_id == BU,
               Application.deleted_at.is_(None), Application.stage.in_(ACTIVE_STAGES))
        .order_by(Application.updated_at.asc())
    ).all()

    queue, breaching, breached = [], 0, 0
    for a, cand, job in rows:
        updated = a.updated_at or a.created_at or now
        age_hours = max(0.0, (now - updated).total_seconds() / 3600.0)
        sla = _sla(age_hours)
        if sla == "warning":
            breaching += 1
        elif sla == "breached":
            breached += 1
        queue.append({
            "id": str(a.id), "candidate": cand.full_name, "job": job.title,
            "stage": a.stage, "ageHours": round(age_hours, 1), "sla": sla,
            "slaTargetHours": SLA_TARGET_HOURS,
        })

    return {"open": len(queue), "breaching": breaching, "breached": breached, "queue": queue}
