"""Notification delivery-status read (B.10) — staff-gated, tenant-scoped debugging
view of the enqueue/delivery ledger. Never exposes other tenants' rows."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..models import Notification
from .staffing import _require_staff, _tid

router = APIRouter()


@router.get("/notifications")
def list_notifications(status: str | None = Query(default=None),
                       limit: int = Query(default=50, le=200),
                       ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db)):
    _require_staff(ctx)
    stmt = select(Notification).where(Notification.tenant_id == _tid(ctx))
    if status:
        stmt = stmt.where(Notification.status == status)
    rows = db.execute(stmt.order_by(Notification.created_at.desc()).limit(limit)).scalars().all()
    return [{"id": str(n.id), "template_code": n.template_code, "channel_type": n.channel_type,
             "recipient": n.recipient, "status": n.status, "attempts": n.attempts,
             "last_error": n.last_error,
             "created_at": n.created_at.isoformat() if n.created_at else None,
             "sent_at": n.sent_at.isoformat() if n.sent_at else None} for n in rows]
