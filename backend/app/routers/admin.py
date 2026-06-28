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

import datetime

from fastapi import Header
from pydantic import BaseModel, field_validator

from .. import erasure
from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models import AuditLog, ClientRegistrationRequest, ClientUser, Consent, DpdpRequest, User
from ..models_staffing import Candidate, Client, Job
from ..security import hash_password
from ..validation import validate_password

router = APIRouter()
BU = "STAFFING"
ADMIN_ROLES = {"owner", "super_admin", "admin"}


def _require_admin(ctx: RequestContext):
    # A client-portal session (client_id bound) is never an admin.
    if ctx.client_id is not None or not (set(ctx.roles) & ADMIN_ROLES):
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


# ── DPDP erasure manual gate (admin) ─────────────────────────────
def _req_dict(r: DpdpRequest) -> dict:
    return {"id": str(r.id), "kind": r.kind, "status": r.status, "legal_hold": r.legal_hold,
            "subject_user_id": str(r.subject_user_id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None}


def _load_erasure(db, ctx, request_id: uuid.UUID) -> DpdpRequest:
    r = db.execute(select(DpdpRequest).where(
        DpdpRequest.id == request_id, DpdpRequest.tenant_id == _tid(ctx),
        DpdpRequest.kind == "erasure")).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Erasure request not found"})
    return r


@router.get("/erasure-requests")
def erasure_requests(limit: int = Query(50, le=200), offset: int = 0,
                     ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_admin(ctx)
    where = [DpdpRequest.tenant_id == _tid(ctx), DpdpRequest.kind == "erasure"]
    base = select(DpdpRequest).where(*where).order_by(DpdpRequest.created_at.desc())
    cnt = select(func.count()).select_from(DpdpRequest).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: _req_dict(r[0]))


@router.post("/erasure-requests/{request_id}/legal-hold")
def flag_legal_hold(request_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    """Flag a request as legal-hold — exempt from processing until manual approval."""
    _require_admin(ctx)
    r = _load_erasure(db, ctx, request_id)
    if r.status in (erasure.COMPLETED, erasure.REJECTED):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"Cannot hold a {r.status} request"})
    r.legal_hold = True
    r.status = erasure.LEGAL_HOLD
    db.commit()
    return _req_dict(r)


@router.post("/erasure-requests/{request_id}/approve")
def approve_erasure(request_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    """Explicit manual approval → anonymize. Works for pending or legal_hold (this IS
    the explicit approval that clears the hold). No-op-safe on already-completed."""
    _require_admin(ctx)
    r = _load_erasure(db, ctx, request_id)
    if r.status in (erasure.COMPLETED, erasure.REJECTED):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"Request already {r.status}"})
    user = db.execute(select(User).where(User.id == r.subject_user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Subject user not found"})
    r.legal_hold = False
    r.status = erasure.APPROVED
    db.flush()
    summary = erasure.run_erasure(db, ctx, r, user)
    db.commit()
    return {**_req_dict(r), "summary": summary}


@router.post("/erasure-requests/{request_id}/reject")
def reject_erasure(request_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db)):
    _require_admin(ctx)
    r = _load_erasure(db, ctx, request_id)
    if r.status in (erasure.COMPLETED, erasure.REJECTED):
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"Request already {r.status}"})
    r.status = erasure.REJECTED
    db.commit()
    return _req_dict(r)


# ── Client self-registration approval (the security gate) ────────
def _reg_dict(r: ClientRegistrationRequest) -> dict:
    return {"id": str(r.id), "company_name": r.company_name, "industry": r.industry,
            "contact_person": r.contact_person, "email": str(r.email),
            "phone": "••••••" if r.phone_bidx is not None else None,  # masked, no decrypt
            "website": r.website, "company_size": r.company_size, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None}


class ApproveClientIn(BaseModel):
    client_id: uuid.UUID | None = None       # link to an existing clients row …
    create_new_client: bool = False          # … or create one from the company name
    initial_password: str                    # admin-set initial credential for the client login

    @field_validator("initial_password")
    @classmethod
    def _pw(cls, v):
        return validate_password(v)


@router.get("/client-registrations")
def client_registrations(status: str | None = Query(default=None), limit: int = Query(50, le=200), offset: int = 0,
                         ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Admin queue of client self-registration requests (pending first)."""
    _require_admin(ctx)
    where = [ClientRegistrationRequest.tenant_id == _tid(ctx)]
    if status:
        where.append(ClientRegistrationRequest.status == status)
    base = (select(ClientRegistrationRequest).where(*where)
            .order_by((ClientRegistrationRequest.status == "pending").desc(),
                      ClientRegistrationRequest.created_at.desc()))
    cnt = select(func.count()).select_from(ClientRegistrationRequest).where(*where)
    return _page(db, base, cnt, limit, offset, lambda r: _reg_dict(r[0]))


def _load_reg(db, ctx, req_id):
    r = db.execute(select(ClientRegistrationRequest).where(
        ClientRegistrationRequest.id == req_id, ClientRegistrationRequest.tenant_id == _tid(ctx))).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Registration request not found"})
    return r


@router.post("/client-registrations/{req_id}/approve")
def approve_client(req_id: uuid.UUID, body: ApproveClientIn, ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """THE SECURITY GATE: link the registrant to a client + activate their login.
    Creates the user (active) + an ACTIVE client_users binding (tenant_id+client_id).
    Only this explicit approval grants a client a scoped session."""
    _require_admin(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    r = _load_reg(db, ctx, req_id)
    if r.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"Request already {r.status}"})

    # 1) resolve the client (existing or new)
    if body.client_id is not None:
        client = db.execute(select(Client).where(Client.id == body.client_id, Client.tenant_id == _tid(ctx),
                                                 Client.deleted_at.is_(None))).scalar_one_or_none()
        if client is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Client not found"})
    elif body.create_new_client:
        client = Client(tenant_id=_tid(ctx), business_unit_id=BU, name=r.company_name, industry=r.industry)
        db.add(client); db.flush()
    else:
        raise HTTPException(status_code=422, detail={"code": "CLIENT_REQUIRED",
                            "message": "Provide client_id or set create_new_client"})

    # 2) create the login user (must not already exist in this tenant)
    if db.execute(select(User).where(User.tenant_id == _tid(ctx), User.email == r.email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"code": "USER_EXISTS", "message": "A user with this email already exists"})
    user = User(tenant_id=_tid(ctx), email=str(r.email), password_hash=hash_password(body.initial_password),
                full_name=r.contact_person, status="active")
    db.add(user); db.flush()

    # 3) ACTIVE client_users binding — this is what gives the login its client scope
    db.add(ClientUser(tenant_id=_tid(ctx), user_id=user.id, client_id=client.id, status="active"))
    # 4) consent ledger entry for the now-real user
    if r.consent_data_processing:
        db.add(Consent(tenant_id=_tid(ctx), subject_user_id=user.id, purpose="data_processing",
                       granted=True, policy_version=r.policy_version or "2026-06-stub"))

    r.status = "approved"; r.reviewed_by = uuid.UUID(str(ctx.user_id)) if ctx.user_id else None
    r.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    write_audit(db, ctx, "client.approve", "client_registration_request", r.id,
                after={"client_id": str(client.id), "user_id": str(user.id)})
    db.commit()
    res = {"status": "approved", "client_id": str(client.id), "user_email": str(r.email)}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.post("/client-registrations/{req_id}/reject")
def reject_client(req_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                  db: Session = Depends(get_db)):
    _require_admin(ctx)
    r = _load_reg(db, ctx, req_id)
    if r.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": f"Request already {r.status}"})
    r.status = "rejected"; r.reviewed_by = uuid.UUID(str(ctx.user_id)) if ctx.user_id else None
    r.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    write_audit(db, ctx, "client.reject", "client_registration_request", r.id)
    db.commit()
    return _reg_dict(r)
