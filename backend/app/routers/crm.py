"""CRM / lead management (B.12) — shared-schema, BU-scoped, staff-gated.

The lead state machine is a MINI GUARD in the pipeline.py shape: one transition
function, an ALLOWED map, illegal → 409, LOST requires a reason (mirrors B.5
drop/withdraw), won/lost terminal. Stage writes exist nowhere else.

Convert is BRANCHED BY BU: the STAFFING branch (client + optional job intake) is
built; the CONSULTING branch (account/contact/opportunity) is TODO(B.18) and
returns 400 NOT_BUILT until then. Convert requires stage='won' and is idempotent
via converted_client_id — a double convert returns the existing client.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models import Activity, Lead, LEAD_STAGES
from ..models_staffing import Client, Job
from .staffing import _require_staff, _tid

router = APIRouter()

# Mini guard (pipeline.py shape): linear forward path; lost from any non-terminal
# stage WITH a reason; won/lost terminal.
LEAD_TRANSITIONS: dict[str, set[str]] = {
    "new": {"qualified"},
    "qualified": {"proposal"},
    "proposal": {"negotiation"},
    "negotiation": {"won"},
    "won": set(),
    "lost": set(),
}
TERMINAL = frozenset({"won", "lost"})


def _bu(ctx: RequestContext) -> str:
    return ctx.business_unit_id or "STAFFING"


def _err(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _lead_or_404(db: Session, ctx: RequestContext, lead_id: uuid.UUID) -> Lead:
    lead = db.execute(select(Lead).where(
        Lead.id == lead_id, Lead.tenant_id == _tid(ctx),
        Lead.business_unit_id == _bu(ctx),           # BU scoping — the anti-fork
        Lead.deleted_at.is_(None))).scalar_one_or_none()
    if lead is None:
        raise _err(404, "NOT_FOUND", "Lead not found")
    return lead


def _lead_dict(x: Lead) -> dict:
    return {"id": str(x.id), "company": x.company, "contact_name": x.contact_name,
            "contact_email": x.contact_email, "contact_phone": x.contact_phone,
            "source": x.source, "owner_id": str(x.owner_id) if x.owner_id else None,
            "stage": x.stage, "lost_reason": x.lost_reason,
            "converted_client_id": str(x.converted_client_id) if x.converted_client_id else None,
            "business_unit_id": x.business_unit_id,
            "created_at": x.created_at.isoformat() if x.created_at else None}


def _activity(db, ctx, lead: Lead, type_: str, notes: str | None = None):
    db.add(Activity(tenant_id=_tid(ctx), business_unit_id=lead.business_unit_id,
                    lead_id=lead.id, type=type_, notes=notes,
                    actor_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None))


def transition_lead(db: Session, ctx: RequestContext, lead: Lead,
                    to_stage: str, reason: str | None = None) -> Lead:
    """THE only stage writer for leads (mini guard)."""
    if to_stage not in LEAD_STAGES:
        raise _err(422, "VALIDATION_ERROR", f"Unknown stage '{to_stage}'")
    if lead.stage in TERMINAL:
        raise _err(409, "ILLEGAL_TRANSITION", f"'{lead.stage}' is terminal")
    if to_stage == "lost":
        if not (reason and reason.strip()):
            raise _err(422, "REASON_REQUIRED", "A reason is required to mark a lead lost")
        lead.lost_reason = reason.strip()
    elif to_stage not in LEAD_TRANSITIONS.get(lead.stage, set()):
        raise _err(409, "ILLEGAL_TRANSITION", f"Cannot move {lead.stage} → {to_stage}")
    src = lead.stage
    lead.stage = to_stage
    _activity(db, ctx, lead, "stage_change",
              f"{src} → {to_stage}" + (f" ({reason.strip()})" if reason else ""))
    write_audit(db, ctx, "lead.stage_change", "lead", lead.id,
                before={"stage": src},
                after={"stage": to_stage, **({"reason": reason} if reason else {})})
    return lead


# ── CRUD ─────────────────────────────────────────────────────────
class LeadIn(BaseModel):
    company: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    source: str | None = None

    @field_validator("company")
    @classmethod
    def _c(cls, v):
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("Company is required (min 2 characters)")
        return v


class LeadUpdateIn(BaseModel):
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    source: str | None = None


@router.post("/leads")
def create_lead(body: LeadIn, ctx: RequestContext = Depends(get_current_context),
                db: Session = Depends(get_db),
                idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    lead = Lead(tenant_id=_tid(ctx), business_unit_id=_bu(ctx), company=body.company,
                contact_name=body.contact_name, contact_email=body.contact_email,
                contact_phone=body.contact_phone, source=body.source,
                owner_id=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(lead)
    db.flush()
    _activity(db, ctx, lead, "created", f"Lead created ({body.source or 'no source'})")
    write_audit(db, ctx, "lead.create", "lead", lead.id, after={"company": lead.company})
    db.commit()
    res = _lead_dict(lead)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/leads")
def list_leads(stage: str | None = Query(default=None),
               owner_id: uuid.UUID | None = Query(default=None),
               ctx: RequestContext = Depends(get_current_context),
               db: Session = Depends(get_db)):
    """Pipeline/list view — tenant + BU scoped (a staffing session sees ONLY
    STAFFING leads; a future consulting session only CONSULTING ones)."""
    _require_staff(ctx)
    stmt = select(Lead).where(Lead.tenant_id == _tid(ctx),
                              Lead.business_unit_id == _bu(ctx),
                              Lead.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(Lead.stage == stage)
    if owner_id:
        stmt = stmt.where(Lead.owner_id == owner_id)
    rows = db.execute(stmt.order_by(Lead.created_at.desc()).limit(200)).scalars().all()
    return [_lead_dict(x) for x in rows]


@router.get("/leads/{lead_id}")
def get_lead(lead_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
             db: Session = Depends(get_db)):
    _require_staff(ctx)
    return _lead_dict(_lead_or_404(db, ctx, lead_id))


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: uuid.UUID, body: LeadUpdateIn,
                ctx: RequestContext = Depends(get_current_context),
                db: Session = Depends(get_db)):
    """Non-stage fields only — stage moves go through /transition (the guard)."""
    _require_staff(ctx)
    lead = _lead_or_404(db, ctx, lead_id)
    for field in ("contact_name", "contact_email", "contact_phone", "source"):
        v = getattr(body, field)
        if v is not None:
            setattr(lead, field, v)
    write_audit(db, ctx, "lead.update", "lead", lead.id, after={"fields": "contact/source"})
    db.commit()
    return _lead_dict(lead)


# ── transitions ──────────────────────────────────────────────────
class LeadTransitionIn(BaseModel):
    to_stage: str
    reason: str | None = None


@router.post("/leads/{lead_id}/transition")
def lead_transition(lead_id: uuid.UUID, body: LeadTransitionIn,
                    ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    lead = _lead_or_404(db, ctx, lead_id)
    transition_lead(db, ctx, lead, body.to_stage, body.reason)
    db.commit()
    res = _lead_dict(lead)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


# ── activities ───────────────────────────────────────────────────
class ActivityIn(BaseModel):
    type: str            # call | email | meeting | note | ...
    notes: str | None = None


@router.post("/leads/{lead_id}/activities")
def log_activity(lead_id: uuid.UUID, body: ActivityIn,
                 ctx: RequestContext = Depends(get_current_context),
                 db: Session = Depends(get_db),
                 idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    lead = _lead_or_404(db, ctx, lead_id)
    _activity(db, ctx, lead, body.type, body.notes)
    db.commit()
    res = {"lead_id": str(lead.id), "type": body.type, "logged": True}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/leads/{lead_id}/activities")
def list_activities(lead_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    _require_staff(ctx)
    lead = _lead_or_404(db, ctx, lead_id)
    rows = db.execute(select(Activity).where(Activity.lead_id == lead.id)
                      .order_by(Activity.occurred_at.asc())).scalars().all()
    return [{"id": str(a.id), "type": a.type, "notes": a.notes,
             "actor_id": str(a.actor_id) if a.actor_id else None,
             "occurred_at": a.occurred_at.isoformat()} for a in rows]


# ── convert (STAFFING branch; CONSULTING = TODO(B.18)) ──────────
class ConvertIn(BaseModel):
    job_title: str | None = None      # optional job intake


@router.patch("/leads/{lead_id}/convert")
def convert_lead(lead_id: uuid.UUID, body: ConvertIn,
                 ctx: RequestContext = Depends(get_current_context),
                 db: Session = Depends(get_db),
                 idempotency_key: str | None = Header(default=None)):
    """WON staffing lead → staffing client (+ optional job intake). Idempotent:
    converted_client_id is the guard — a second convert returns the existing
    client and can never create a duplicate."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    lead = _lead_or_404(db, ctx, lead_id)
    if lead.business_unit_id != "STAFFING":
        # TODO(B.18): CONSULTING branch — account/contact/opportunity creation.
        raise _err(400, "NOT_BUILT",
                   "Convert for this business unit ships with the Consulting vertical (B.18)")
    if lead.converted_client_id is not None:          # idempotency guard
        res = {**_lead_dict(lead), "client_id": str(lead.converted_client_id),
               "already_converted": True}
        store(str(ctx.tenant_id), idempotency_key, res)
        return res
    if lead.stage != "won":
        raise _err(409, "STAGE_INVALID", "Only a WON lead can be converted")

    client = Client(tenant_id=_tid(ctx), business_unit_id="STAFFING", name=lead.company)
    db.add(client)
    db.flush()
    job_id = None
    if body.job_title and body.job_title.strip():
        job = Job(tenant_id=_tid(ctx), business_unit_id="STAFFING",
                  title=body.job_title.strip(), client_id=client.id)
        db.add(job)
        db.flush()
        job_id = str(job.id)
    lead.converted_client_id = client.id
    _activity(db, ctx, lead, "converted",
              f"Converted to client {client.id}" + (f" + job intake {job_id}" if job_id else ""))
    write_audit(db, ctx, "lead.convert", "lead", lead.id,
                after={"client_id": str(client.id), **({"job_id": job_id} if job_id else {})})
    db.commit()
    res = {**_lead_dict(lead), "client_id": str(client.id),
           **({"job_id": job_id} if job_id else {}), "already_converted": False}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res
