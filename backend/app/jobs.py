"""Commercial-layer periodic jobs (B.9) — MATERIALIZERS, never the source of truth.

The guarantee position is always DERIVABLE from placement dates on read
(derived_guarantee_state) — correct even if these jobs never run. The sweep only
materializes `status` flips + timeline events; the status-guarded UPDATE makes a
double run a no-op and a missed run self-heal on the next pass (it catches every
overdue row regardless of the gap).

No scheduler exists in this repo (verified B.9 Part-0): these run via
scripts/run_commercial_jobs.py as a one-off ECS task (the established
migrate/bootstrap pattern). Production wiring = an EventBridge Scheduler rule →
ECS RunTask (small free infra addition, deferred — PENDING).
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .context import RequestContext
from .models_staffing import Invoice, Placement
from .timeline import EventType, emit_timeline

log = logging.getLogger("sps.jobs")


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def derived_guarantee_state(p: Placement, today: dt.date | None = None) -> str:
    """The SOURCE OF TRUTH for the guarantee position — pure date math.
    breached/replaced are explicit terminal facts; otherwise the window decides."""
    if p.status in ("breached", "replaced"):
        return p.status
    today = today or _today()
    return "cleared" if today > p.guarantee_until else "in_guarantee"


def guarantee_sweep(db: Session) -> int:
    """Materialize 'cleared' for active placements whose window has passed and emit
    ONE GuaranteeCompletion each. Idempotent: only status='active' rows flip, so a
    second run (or a run after downtime) can never double-emit."""
    today = _today()
    due = db.execute(select(Placement).where(
        Placement.status == "active", Placement.guarantee_until < today,
        Placement.deleted_at.is_(None))).scalars().all()
    for p in due:
        p.status = "cleared"
        ctx = RequestContext(tenant_id=str(p.tenant_id), business_unit_id="STAFFING",
                             user_id=None, roles=())
        emit_timeline(db, candidate_id=p.candidate_id,
                      event_type=EventType.GUARANTEE_COMPLETION,
                      payload={"placement_id": str(p.id), "outcome": "cleared",
                               "guarantee_until": p.guarantee_until.isoformat()}, ctx=ctx)
    db.commit()
    log.info("guarantee_sweep: cleared=%d", len(due))
    return len(due)


def dunning_sweep(db: Session) -> list[dict]:
    """Detect overdue invoices (draft/issued older than INVOICE_OVERDUE_DAYS, not
    credit notes). DELIVERY IS STUBBED (B.10/SES) — the intended send is logged;
    no state changes, so re-running is trivially idempotent."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.invoice_overdue_days)
    rows = db.execute(select(Invoice).where(
        Invoice.status.in_(("draft", "issued")), Invoice.created_at < cutoff,
        Invoice.credit_note_of.is_(None), Invoice.deleted_at.is_(None))).scalars().all()
    out = []
    for v in rows:
        out.append({"invoice_id": str(v.id), "client_id": str(v.client_id) if v.client_id else None,
                    "total_amount": float(v.total_amount) if v.total_amount is not None else None,
                    "age_days": (dt.datetime.now(dt.timezone.utc) - v.created_at).days})
        log.info("dunning (SEND STUBBED until B.10/SES): invoice %s overdue %d days",
                 v.id, out[-1]["age_days"])
    return out
