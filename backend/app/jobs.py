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


def dunning_sweep(db: Session, enqueue_sends: bool = False) -> list[dict]:
    """Detect overdue invoices (draft/issued older than INVOICE_OVERDUE_DAYS, not
    credit notes). READ-ONLY by default (the /invoices/overdue endpoint); the
    one-off runner passes enqueue_sends=True to ENQUEUE the B.10 dunning
    notification per invoice (stable key 'invoice_dunning:<id>' → one notice per
    invoice; cadence policy is a Part-D decision). Recipient = the client's
    active client_admin email; no bound user → detection only, logged."""
    from .invoice_pdf import provisional_number
    from .models import ClientUser, User
    from . import notify

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.invoice_overdue_days)
    rows = db.execute(select(Invoice).where(
        Invoice.status.in_(("draft", "issued")), Invoice.created_at < cutoff,
        Invoice.credit_note_of.is_(None), Invoice.deleted_at.is_(None))).scalars().all()
    out = []
    for v in rows:
        age = (dt.datetime.now(dt.timezone.utc) - v.created_at).days
        out.append({"invoice_id": str(v.id), "client_id": str(v.client_id) if v.client_id else None,
                    "total_amount": float(v.total_amount) if v.total_amount is not None else None,
                    "age_days": age})
        if not enqueue_sends:
            continue
        recipient = None
        client_name = "Client"
        if v.client_id is not None:
            from .models_staffing import Client
            client = db.get(Client, v.client_id)
            client_name = client.name if client else client_name
            cu = db.execute(select(User.email).join(ClientUser, ClientUser.user_id == User.id)
                            .where(ClientUser.client_id == v.client_id,
                                   ClientUser.status == "active")
                            .order_by(ClientUser.created_at.asc())).scalars().first()
            recipient = cu
        if recipient:
            notify.enqueue(db, template_code="invoice_dunning", recipient=recipient,
                           vars={"client_name": client_name,
                                 "invoice_number": provisional_number(v.id),
                                 "total_amount": f"INR {float(v.total_amount or 0):,.2f}",
                                 "age_days": age},
                           tenant_id=v.tenant_id, idempotency_key=f"invoice_dunning:{v.id}")
        else:
            log.info("dunning: invoice %s overdue %dd — no bound client user, detection only",
                     v.id, age)
    if enqueue_sends:
        db.commit()
    return out
