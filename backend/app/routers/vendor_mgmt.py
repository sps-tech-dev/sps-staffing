"""Vendor depth (B.13): contracts, CLIENT-DYNAMIC commission, scorecards.

Resolution (most-specific wins, settled): per-placement override →
vendor_client_rates (vendor×client) → the vendor_contract valid AT
placement.joined_on → global default (config, shipped None → 409 rather than an
invented rate). Base = the PLACEMENT FEE (SPS earnings share), never CTC.

The commission row is MATERIALIZED (rate lock: later rate/contract changes never
retro-alter it) with lifecycle accrued→paid|void. UNIQUE(placement_id) = one
commission per placement. Replacements accrue nothing (no fee); a credit-noted
invoice refuses accrual, and the credit-note endpoint auto-voids an accrued
commission (no-double-count both directions).
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..config import settings
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..jobs import derived_guarantee_state
from ..models_staffing import (
    Application, Invoice, Placement, Vendor, VendorClientRate, VendorCommission,
    VendorContract, VendorSubmission,
)
from .staffing import BU, _require_staff, _tid

router = APIRouter()


def _err(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _vendor_or_404(db: Session, ctx: RequestContext, vendor_id: uuid.UUID) -> Vendor:
    v = db.execute(select(Vendor).where(Vendor.id == vendor_id, Vendor.tenant_id == _tid(ctx),
                                        Vendor.deleted_at.is_(None))).scalar_one_or_none()
    if v is None:
        raise _err(404, "NOT_FOUND", "Vendor not found")
    return v


def _resolve_commission_percent(db: Session, *, vendor_id, client_id, placement_date,
                                override=None) -> tuple[float, str]:
    """THE resolver (settled order). Returns (percent, source_level).
    Locks to the state valid AT placement_date; raises 409 when nothing resolves."""
    if override is not None:
        return float(override), "placement_override"
    if client_id is not None:
        rate = db.execute(select(VendorClientRate).where(
            VendorClientRate.vendor_id == vendor_id,
            VendorClientRate.client_id == client_id,
            VendorClientRate.deleted_at.is_(None))).scalar_one_or_none()
        if rate is not None:
            return float(rate.commission_percent), "client_rate"
    contract = db.execute(select(VendorContract).where(
        VendorContract.vendor_id == vendor_id,
        VendorContract.status == "active",
        VendorContract.deleted_at.is_(None),
        VendorContract.valid_from <= placement_date,
        (VendorContract.valid_until.is_(None)) | (VendorContract.valid_until >= placement_date))
        .order_by(VendorContract.valid_from.desc())).scalars().first()
    if contract is not None:
        return float(contract.base_commission_percent), "contract_base"
    if settings.vendor_commission_default_percent is not None:
        return float(settings.vendor_commission_default_percent), "global_default"
    raise _err(409, "NO_COMMISSION_BASIS",
               "No override, client rate, valid contract, or global default — "
               "cannot invent a commission rate")


# ── contracts ────────────────────────────────────────────────────
class ContractIn(BaseModel):
    base_commission_percent: float
    valid_from: dt.date
    valid_until: dt.date | None = None


@router.post("/vendors/{vendor_id}/contracts")
def create_contract(vendor_id: uuid.UUID, body: ContractIn,
                    ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    v = _vendor_or_404(db, ctx, vendor_id)
    if body.base_commission_percent <= 0 or body.base_commission_percent >= 100:
        raise _err(422, "VALIDATION_ERROR", "Commission percent must be between 0 and 100")
    ct = VendorContract(tenant_id=_tid(ctx), business_unit_id=BU, vendor_id=v.id,
                        base_commission_percent=body.base_commission_percent,
                        valid_from=body.valid_from, valid_until=body.valid_until)
    db.add(ct)
    db.flush()
    write_audit(db, ctx, "vendor.contract_create", "vendor_contract", ct.id,
                after={"vendor_id": str(v.id), "percent": body.base_commission_percent,
                       "valid_from": body.valid_from.isoformat()})
    db.commit()
    res = {"id": str(ct.id), "vendor_id": str(v.id),
           "base_commission_percent": float(ct.base_commission_percent),
           "valid_from": ct.valid_from.isoformat(),
           "valid_until": ct.valid_until.isoformat() if ct.valid_until else None,
           "status": ct.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/vendors/{vendor_id}/contracts")
def list_contracts(vendor_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db)):
    _require_staff(ctx)
    v = _vendor_or_404(db, ctx, vendor_id)
    rows = db.execute(select(VendorContract).where(
        VendorContract.vendor_id == v.id, VendorContract.deleted_at.is_(None))
        .order_by(VendorContract.valid_from.desc())).scalars().all()
    return [{"id": str(x.id), "base_commission_percent": float(x.base_commission_percent),
             "valid_from": x.valid_from.isoformat(),
             "valid_until": x.valid_until.isoformat() if x.valid_until else None,
             "status": x.status} for x in rows]


# ── client-dynamic rates ─────────────────────────────────────────
class ClientRateIn(BaseModel):
    client_id: uuid.UUID
    commission_percent: float


@router.put("/vendors/{vendor_id}/client-rates")
def set_client_rate(vendor_id: uuid.UUID, body: ClientRateIn,
                    ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    """Upsert the vendor×client rate (the CLIENT-DYNAMIC level)."""
    _require_staff(ctx)
    v = _vendor_or_404(db, ctx, vendor_id)
    if body.commission_percent <= 0 or body.commission_percent >= 100:
        raise _err(422, "VALIDATION_ERROR", "Commission percent must be between 0 and 100")
    row = db.execute(select(VendorClientRate).where(
        VendorClientRate.vendor_id == v.id, VendorClientRate.client_id == body.client_id,
        VendorClientRate.deleted_at.is_(None))).scalar_one_or_none()
    if row is None:
        row = VendorClientRate(tenant_id=_tid(ctx), business_unit_id=BU, vendor_id=v.id,
                               client_id=body.client_id,
                               commission_percent=body.commission_percent)
        db.add(row)
    else:
        row.commission_percent = body.commission_percent
    db.flush()
    write_audit(db, ctx, "vendor.client_rate_set", "vendor_client_rate", row.id,
                after={"vendor_id": str(v.id), "client_id": str(body.client_id),
                       "percent": body.commission_percent})
    db.commit()
    return {"vendor_id": str(v.id), "client_id": str(body.client_id),
            "commission_percent": float(row.commission_percent)}


@router.get("/vendors/{vendor_id}/client-rates")
def list_client_rates(vendor_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db)):
    _require_staff(ctx)
    v = _vendor_or_404(db, ctx, vendor_id)
    rows = db.execute(select(VendorClientRate).where(
        VendorClientRate.vendor_id == v.id,
        VendorClientRate.deleted_at.is_(None))).scalars().all()
    return [{"client_id": str(x.client_id),
             "commission_percent": float(x.commission_percent)} for x in rows]


# ── commission accrual + lifecycle ───────────────────────────────
class AccrueIn(BaseModel):
    vendor_id: uuid.UUID | None = None       # derived from the sourcing trail if omitted
    override_percent: float | None = None    # the most-specific level


@router.post("/placements/{placement_id}/commission")
def accrue_commission(placement_id: uuid.UUID, body: AccrueIn,
                      ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db),
                      idempotency_key: str | None = Header(default=None)):
    """Materialize the commission for a vendor-sourced placement:
    commission = PLACEMENT FEE × resolved%. Refused for replacements (no fee),
    credit-noted placements, or placements without a vendor sourcing trail."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    plc = db.execute(select(Placement).where(
        Placement.id == placement_id, Placement.tenant_id == _tid(ctx),
        Placement.deleted_at.is_(None))).scalar_one_or_none()
    if plc is None:
        raise _err(404, "NOT_FOUND", "Placement not found")
    if plc.replacement_for is not None:
        raise _err(409, "REPLACEMENT_NO_FEE",
                   "A replacement placement has no fee — no commission accrues")
    if db.execute(select(VendorCommission).where(
            VendorCommission.placement_id == plc.id,
            VendorCommission.deleted_at.is_(None))).scalar_one_or_none():
        raise _err(409, "COMMISSION_EXISTS", "A commission already exists for this placement")

    invoice = db.execute(select(Invoice).where(
        Invoice.placement_id == plc.id, Invoice.credit_note_of.is_(None),
        Invoice.deleted_at.is_(None))).scalar_one_or_none()
    if invoice is None or invoice.fee_amount is None:
        raise _err(409, "NO_FEE_INVOICE", "The placement has no fee invoice to base commission on")
    if db.execute(select(Invoice).where(Invoice.credit_note_of == invoice.id,
                                        Invoice.deleted_at.is_(None))).scalar_one_or_none():
        raise _err(409, "CREDIT_NOTED", "The placement's fee has been credit-noted")

    # sourcing trail: the vendor must have actually submitted this candidate
    appn = db.get(Application, plc.application_id)
    trail = select(VendorSubmission).where(
        VendorSubmission.tenant_id == _tid(ctx),
        VendorSubmission.candidate_id == plc.candidate_id,
        VendorSubmission.deleted_at.is_(None))
    if body.vendor_id is not None:
        trail = trail.where(VendorSubmission.vendor_id == body.vendor_id)
    subs = db.execute(trail).scalars().all()
    if appn is not None:
        subs = [s for s in subs if s.job_id is None or s.job_id == appn.job_id]
    if not subs:
        raise _err(409, "NO_SOURCING_TRAIL",
                   "No vendor submission links this vendor to the placed candidate")
    vendor_ids = {s.vendor_id for s in subs}
    if body.vendor_id is None and len(vendor_ids) > 1:
        raise _err(409, "AMBIGUOUS_VENDOR", "Multiple vendors submitted — specify vendor_id")
    vendor_id = body.vendor_id or vendor_ids.pop()

    pct, source = _resolve_commission_percent(
        db, vendor_id=vendor_id, client_id=plc.client_id,
        placement_date=plc.joined_on, override=body.override_percent)
    fee = float(invoice.fee_amount)
    amount = round(fee * pct / 100, 2)
    vc = VendorCommission(tenant_id=_tid(ctx), business_unit_id=BU, vendor_id=vendor_id,
                          placement_id=plc.id, resolved_percent=pct, base_amount=fee,
                          commission_amount=amount)
    db.add(vc)
    db.flush()
    write_audit(db, ctx, "vendor.commission_accrue", "vendor_commission", vc.id,
                after={"vendor_id": str(vendor_id), "placement_id": str(plc.id),
                       "resolved_percent": pct, "source_level": source,
                       "base_fee": fee, "commission": amount})
    db.commit()
    res = {"id": str(vc.id), "vendor_id": str(vendor_id), "placement_id": str(plc.id),
           "resolved_percent": pct, "source_level": source, "base_amount": fee,
           "commission_amount": amount, "status": vc.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


class VoidIn(BaseModel):
    reason: str


@router.post("/vendors/commissions/{commission_id}/void")
def void_commission(commission_id: uuid.UUID, body: VoidIn,
                    ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    _require_staff(ctx)
    if not body.reason.strip():
        raise _err(422, "REASON_REQUIRED", "A reason is required to void a commission")
    vc = db.execute(select(VendorCommission).where(
        VendorCommission.id == commission_id, VendorCommission.tenant_id == _tid(ctx),
        VendorCommission.deleted_at.is_(None))).scalar_one_or_none()
    if vc is None:
        raise _err(404, "NOT_FOUND", "Commission not found")
    if vc.status == "paid":
        raise _err(409, "ALREADY_PAID", "A paid commission cannot be voided here")
    vc.status = "void"
    vc.void_reason = body.reason.strip()
    write_audit(db, ctx, "vendor.commission_void", "vendor_commission", vc.id,
                after={"reason": vc.void_reason})
    db.commit()
    return {"id": str(vc.id), "status": vc.status, "void_reason": vc.void_reason}


@router.post("/vendors/commissions/{commission_id}/mark-paid")
def mark_paid(commission_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
              db: Session = Depends(get_db)):
    """Lifecycle only — actual payout/money movement is Part D."""
    _require_staff(ctx)
    vc = db.execute(select(VendorCommission).where(
        VendorCommission.id == commission_id, VendorCommission.tenant_id == _tid(ctx),
        VendorCommission.deleted_at.is_(None))).scalar_one_or_none()
    if vc is None:
        raise _err(404, "NOT_FOUND", "Commission not found")
    if vc.status != "accrued":
        raise _err(409, "NOT_ACCRUED", f"Only an accrued commission can be paid (is '{vc.status}')")
    vc.status = "paid"
    write_audit(db, ctx, "vendor.commission_paid", "vendor_commission", vc.id, after={})
    db.commit()
    return {"id": str(vc.id), "status": vc.status}


@router.get("/vendors/{vendor_id}/commissions")
def list_commissions(vendor_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db)):
    _require_staff(ctx)
    v = _vendor_or_404(db, ctx, vendor_id)
    rows = db.execute(select(VendorCommission).where(
        VendorCommission.vendor_id == v.id, VendorCommission.deleted_at.is_(None))
        .order_by(VendorCommission.computed_at.desc())).scalars().all()
    return [{"id": str(x.id), "placement_id": str(x.placement_id),
             "resolved_percent": float(x.resolved_percent),
             "base_amount": float(x.base_amount),
             "commission_amount": float(x.commission_amount), "status": x.status,
             "void_reason": x.void_reason} for x in rows]


# ── performance scorecard (read-model on-read; B.11 pattern, no table) ──
@router.get("/vendors/{vendor_id}/scorecard")
def scorecard(vendor_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
              db: Session = Depends(get_db)):
    _require_staff(ctx)
    v = _vendor_or_404(db, ctx, vendor_id)
    n_subs = db.execute(select(func.count()).select_from(VendorSubmission).where(
        VendorSubmission.vendor_id == v.id,
        VendorSubmission.deleted_at.is_(None))).scalar_one()
    commissions = db.execute(select(VendorCommission).where(
        VendorCommission.vendor_id == v.id,
        VendorCommission.deleted_at.is_(None))).scalars().all()
    placement_ids = [c.placement_id for c in commissions]
    placements = db.execute(select(Placement).where(
        Placement.id.in_(placement_ids))).scalars().all() if placement_ids else []
    fills = []
    for p in placements:
        sub = db.execute(select(VendorSubmission).where(
            VendorSubmission.vendor_id == v.id,
            VendorSubmission.candidate_id == p.candidate_id)
            .order_by(VendorSubmission.created_at.asc())).scalars().first()
        if sub is not None:
            fills.append((p.joined_on - sub.created_at.date()).days)
    active = sum(1 for p in placements if derived_guarantee_state(p) == "in_guarantee")
    return {"vendor_id": str(v.id), "submissions": n_subs,
            "placements": len(placements),
            "conversion_rate": round(len(placements) / n_subs, 4) if n_subs else None,
            "avg_time_to_fill_days": round(sum(fills) / len(fills), 1) if fills else None,
            "active_in_guarantee": active,
            "commission_accrued": sum(float(c.commission_amount) for c in commissions
                                      if c.status == "accrued"),
            "commission_paid": sum(float(c.commission_amount) for c in commissions
                                   if c.status == "paid")}
