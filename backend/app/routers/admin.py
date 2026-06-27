"""Admin console read surfaces (Part 17 / Appendix D.1, F4).

Paginated, tenant-scoped lists for candidates / clients / jobs / audit_logs.
Admin-gated (owner/super_admin/admin only — stricter than the staff gate).
Read-only here; candidate creation (with PAN) is the registration slice, where
the PII-encryption blocker applies.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..models import AuditLog
from ..models_staffing import Candidate, Client, Job

router = APIRouter()
BU = "STAFFING"
ADMIN_ROLES = {"owner", "super_admin", "admin"}


def _require_admin(ctx: RequestContext):
    if not (set(ctx.roles) & ADMIN_ROLES):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Admin role required"})


def _tid(ctx): return uuid.UUID(str(ctx.tenant_id))


def _page(db, base_stmt, count_stmt, limit, offset, to_dict):
    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(base_stmt.limit(limit).offset(offset)).all()
    return {"items": [to_dict(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/candidates")
def candidates(q: str | None = Query(default=None), limit: int = Query(20, le=100), offset: int = 0,
               ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_admin(ctx)
    where = [Candidate.tenant_id == _tid(ctx), Candidate.deleted_at.is_(None)]
    if q:
        where.append(Candidate.full_name.ilike(f"%{q}%"))
    base = select(Candidate).where(*where).order_by(Candidate.created_at.desc())
    cnt = select(func.count()).select_from(Candidate).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: {
        "id": str(r[0].id), "full_name": r[0].full_name, "email": r[0].email,
        # PII: phone is encrypted (Part 10) + deferred. Show only PRESENCE (masked)
        # via the non-sensitive blind index — no decryption in the list. A full
        # reveal is a separate privileged, audited path.
        "phone": "••••••" if r[0].phone_bidx is not None else None, "skills": r[0].skills,
        "total_exp": float(r[0].total_exp) if r[0].total_exp is not None else None,
        "created_at": r[0].created_at.isoformat() if r[0].created_at else None,
    })


@router.get("/clients")
def clients(limit: int = Query(20, le=100), offset: int = 0,
            ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_admin(ctx)
    where = [Client.tenant_id == _tid(ctx), Client.business_unit_id == BU, Client.deleted_at.is_(None)]
    base = select(Client).where(*where).order_by(Client.created_at.desc())
    cnt = select(func.count()).select_from(Client).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: {
        "id": str(r[0].id), "name": r[0].name, "industry": r[0].industry, "status": r[0].status})


@router.get("/jobs")
def jobs(status: str | None = Query(default=None), limit: int = Query(20, le=100), offset: int = 0,
         ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_admin(ctx)
    where = [Job.tenant_id == _tid(ctx), Job.business_unit_id == BU, Job.deleted_at.is_(None)]
    if status:
        where.append(Job.status == status)
    base = select(Job).where(*where).order_by(Job.created_at.desc())
    cnt = select(func.count()).select_from(Job).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: {
        "id": str(r[0].id), "title": r[0].title, "status": r[0].status})


@router.get("/audit-logs")
def audit_logs(limit: int = Query(50, le=200), offset: int = 0,
               ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_admin(ctx)
    where = [AuditLog.tenant_id == _tid(ctx)]
    base = select(AuditLog).where(*where).order_by(AuditLog.ts.desc())
    cnt = select(func.count()).select_from(AuditLog).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: {
        "id": r[0].id, "action": r[0].action, "entity": r[0].entity,
        "entity_id": str(r[0].entity_id) if r[0].entity_id else None,
        "actor_id": str(r[0].actor_id) if r[0].actor_id else None,
        "ts": r[0].ts.isoformat() if r[0].ts else None})
