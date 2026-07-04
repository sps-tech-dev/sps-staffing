"""Commercial layer endpoints (B.9): placements, guarantee, replacement, commission,
invoice PDF + credit-note structure, overdue detection. Staff-gated, tenant-scoped.

Fee model (founder-confirmed, Part 0-FEE): base = ANNUAL CTC; fee = annual_ctc ×
resolved% / 100; resolution order per-call override → client.fee_percent → 15;
GST/TDS inert until C.3. A REPLACEMENT placement raises NO invoice (no double fee).
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import invoice_pdf, storage
from ..audit import write_audit
from ..config import settings
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..jobs import derived_guarantee_state, dunning_sweep
from ..models_staffing import (
    DEFAULT_FEE_PERCENT, Application, Candidate, Client, Invoice, Job, Offer, Placement,
)
from ..timeline import EventType, emit_timeline
from .staffing import BU, _require_staff, _tid
from .workflow import _compute_invoice

router = APIRouter()


def _err(status, code, message):
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def _plc_dict(p: Placement) -> dict:
    return {"id": str(p.id), "application_id": str(p.application_id),
            "candidate_id": str(p.candidate_id),
            "client_id": str(p.client_id) if p.client_id else None,
            "recruiter_id": str(p.recruiter_id) if p.recruiter_id else None,
            "offered_ctc": float(p.offered_ctc), "joined_on": p.joined_on.isoformat(),
            "guarantee_until": p.guarantee_until.isoformat(),
            "status": p.status, "derived_state": derived_guarantee_state(p),
            "replacement_for": str(p.replacement_for) if p.replacement_for else None,
            "breach_reason": p.breach_reason}


def _resolve_fee_percent(override, client: Client | None) -> float:
    """Part 0-FEE #3: invoice override → client.fee_percent → global default 15."""
    if override is not None:
        return float(override)
    if client is not None and client.fee_percent is not None:
        return float(client.fee_percent)
    return float(DEFAULT_FEE_PERCENT)


class PlacementIn(BaseModel):
    offered_ctc: float | None = None      # defaults to the accepted offer's ANNUAL CTC
    joined_on: dt.date | None = None      # defaults to offer.joining_date or today
    fee_percent: float | None = None      # per-invoice override (beats client rate)


@router.post("/applications/{app_id}/placement")
def create_placement(app_id: uuid.UUID, body: PlacementIn,
                     ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db),
                     idempotency_key: str | None = Header(default=None)):
    """Client-confirmed joining → placement + guarantee clock + the fee invoice
    (annual CTC × resolved%), Joining timeline event, recruiter attribution.
    Requires the application to be at stage 'joined' (the guard moved it there)."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    appn = db.execute(select(Application).where(
        Application.id == app_id, Application.tenant_id == _tid(ctx),
        Application.business_unit_id == BU,
        Application.deleted_at.is_(None))).scalar_one_or_none()
    if appn is None:
        raise _err(404, "NOT_FOUND", "Application not found")
    if appn.stage != "joined":
        raise _err(409, "STAGE_INVALID", "Application must be at 'joined' to record a placement")
    if db.execute(select(Placement).where(Placement.application_id == appn.id,
                                          Placement.deleted_at.is_(None))).scalar_one_or_none():
        raise _err(409, "PLACEMENT_EXISTS", "A placement already exists for this application")

    offer = db.execute(select(Offer).where(Offer.application_id == appn.id,
                                           Offer.deleted_at.is_(None))
                       .order_by(Offer.created_at.desc())).scalars().first()
    ctc = body.offered_ctc if body.offered_ctc is not None else (
        float(offer.ctc) if offer and offer.ctc is not None else None)
    if ctc is None or ctc <= 0:
        raise _err(422, "CTC_REQUIRED",
                   "Annual CTC is required (none on the offer; supply offered_ctc)")
    joined_on = body.joined_on or (offer.joining_date if offer and offer.joining_date else _today())
    client = db.get(Client, appn.client_id) if appn.client_id else None

    plc = Placement(tenant_id=_tid(ctx), business_unit_id=BU, application_id=appn.id,
                    client_id=appn.client_id, candidate_id=appn.candidate_id,
                    recruiter_id=appn.owner_id, offered_ctc=ctc, joined_on=joined_on,
                    guarantee_until=joined_on + dt.timedelta(days=settings.placement_guarantee_days))
    db.add(plc)
    db.flush()

    fee_pct = _resolve_fee_percent(body.fee_percent, client)
    fee, gst, tds, total = _compute_invoice(ctc, fee_pct, None, None)   # taxes inert (C.3)
    inv = Invoice(tenant_id=_tid(ctx), business_unit_id=BU, application_id=appn.id,
                  client_id=appn.client_id, placement_id=plc.id, base_amount=ctc,
                  fee_percent=fee_pct, fee_amount=fee, total_amount=total, status="draft")
    db.add(inv)
    db.flush()
    emit_timeline(db, candidate_id=appn.candidate_id, event_type=EventType.JOINING,
                  payload={"placement_id": str(plc.id), "application_id": str(appn.id),
                           "joined_on": joined_on.isoformat(),
                           "guarantee_until": plc.guarantee_until.isoformat()}, ctx=ctx)
    write_audit(db, ctx, "placement.create", "placement", plc.id,
                after={"application_id": str(appn.id), "annual_ctc": ctc,
                       "fee_percent": fee_pct, "fee_amount": fee,
                       "invoice_id": str(inv.id)})
    db.commit()
    res = {**_plc_dict(plc), "invoice_id": str(inv.id), "fee_percent": fee_pct,
           "fee_amount": fee, "total_amount": total}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/placements")
def list_placements(ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    _require_staff(ctx)
    rows = db.execute(select(Placement).where(Placement.tenant_id == _tid(ctx),
                                              Placement.deleted_at.is_(None))
                      .order_by(Placement.created_at.desc()).limit(100)).scalars().all()
    return [_plc_dict(p) for p in rows]


class BreachIn(BaseModel):
    reason: str


@router.post("/placements/{placement_id}/breach")
def record_breach(placement_id: uuid.UUID, body: BreachIn,
                  ctx: RequestContext = Depends(get_current_context),
                  db: Session = Depends(get_db),
                  idempotency_key: str | None = Header(default=None)):
    """Candidate left within the guarantee window (staff-recorded fact). Marks the
    placement breached and REOPENS THE REQUISITION — i.e. sets the existing
    jobs.status back to 'open' (no new pipeline edge is invented; the placed
    application's stage is history and stays)."""
    _require_staff(ctx)
    if not body.reason.strip():
        raise _err(422, "REASON_REQUIRED", "A reason is required to record a breach")
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    p = db.execute(select(Placement).where(Placement.id == placement_id,
                                           Placement.tenant_id == _tid(ctx),
                                           Placement.deleted_at.is_(None))).scalar_one_or_none()
    if p is None:
        raise _err(404, "NOT_FOUND", "Placement not found")
    if derived_guarantee_state(p) != "in_guarantee":
        raise _err(409, "NOT_IN_GUARANTEE",
                   f"Placement is '{derived_guarantee_state(p)}' — breach applies only within the window")
    p.status = "breached"
    p.breach_reason = body.reason.strip()
    appn = db.get(Application, p.application_id)
    job = db.get(Job, appn.job_id) if appn else None
    if job is not None and job.status != "open":
        job.status = "open"                      # reopen the requisition (existing flag)
    emit_timeline(db, candidate_id=p.candidate_id, event_type=EventType.GUARANTEE_COMPLETION,
                  payload={"placement_id": str(p.id), "outcome": "breached",
                           "reason": p.breach_reason}, ctx=ctx)
    write_audit(db, ctx, "placement.breach", "placement", p.id,
                after={"reason": p.breach_reason, "job_reopened": bool(job)})
    db.commit()
    res = _plc_dict(p)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


class ReplacementIn(BaseModel):
    application_id: uuid.UUID


@router.post("/placements/{placement_id}/replacement")
def create_replacement(placement_id: uuid.UUID, body: ReplacementIn,
                       ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db),
                       idempotency_key: str | None = Header(default=None)):
    """Link a replacement placement to a BREACHED original. NO-DOUBLE-FEE rule:
    the original's fee was already billed → the replacement raises NO invoice.
    Original → status 'replaced'. Fresh 60-day guarantee for the replacement."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    orig = db.execute(select(Placement).where(Placement.id == placement_id,
                                              Placement.tenant_id == _tid(ctx),
                                              Placement.deleted_at.is_(None))).scalar_one_or_none()
    if orig is None:
        raise _err(404, "NOT_FOUND", "Placement not found")
    if orig.status != "breached":
        raise _err(409, "NOT_BREACHED", "Only a breached placement can be replaced")
    appn = db.execute(select(Application).where(
        Application.id == body.application_id, Application.tenant_id == _tid(ctx),
        Application.deleted_at.is_(None))).scalar_one_or_none()
    if appn is None:
        raise _err(404, "NOT_FOUND", "Replacement application not found")
    orig_app = db.get(Application, orig.application_id)
    if orig_app is None or appn.job_id != orig_app.job_id:
        raise _err(422, "JOB_MISMATCH", "Replacement must be for the same job/requisition")
    if appn.stage != "joined":
        raise _err(409, "STAGE_INVALID", "Replacement application must be at 'joined'")
    if db.execute(select(Placement).where(Placement.application_id == appn.id,
                                          Placement.deleted_at.is_(None))).scalar_one_or_none():
        raise _err(409, "PLACEMENT_EXISTS", "That application already has a placement")

    offer = db.execute(select(Offer).where(Offer.application_id == appn.id,
                                           Offer.deleted_at.is_(None))
                       .order_by(Offer.created_at.desc())).scalars().first()
    ctc = float(offer.ctc) if offer and offer.ctc is not None else float(orig.offered_ctc)
    joined_on = (offer.joining_date if offer and offer.joining_date else _today())
    repl = Placement(tenant_id=_tid(ctx), business_unit_id=BU, application_id=appn.id,
                     client_id=appn.client_id, candidate_id=appn.candidate_id,
                     recruiter_id=appn.owner_id, offered_ctc=ctc, joined_on=joined_on,
                     guarantee_until=joined_on + dt.timedelta(days=settings.placement_guarantee_days),
                     replacement_for=orig.id)
    db.add(repl)
    orig.status = "replaced"
    db.flush()
    # NO invoice here — the no-double-fee rule. (A credit note against the original
    # is a separate, explicit action.)
    emit_timeline(db, candidate_id=appn.candidate_id, event_type=EventType.JOINING,
                  payload={"placement_id": str(repl.id), "application_id": str(appn.id),
                           "joined_on": joined_on.isoformat(),
                           "replacement_for": str(orig.id)}, ctx=ctx)
    write_audit(db, ctx, "placement.replacement", "placement", repl.id,
                after={"replacement_for": str(orig.id), "fee_exempt": True})
    db.commit()
    res = {**_plc_dict(repl), "fee_exempt": True}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/placements/commissions")
def commissions(ctx: RequestContext = Depends(get_current_context),
                db: Session = Depends(get_db)):
    """Recruiter commission attribution (computation only — payout is out of scope):
    per-recruiter placement count + billed fee sum (invoices linked by placement_id,
    credit notes excluded, replacements naturally absent — they have no invoice)."""
    _require_staff(ctx)
    rows = db.execute(
        select(Placement.recruiter_id,
               func.count(func.distinct(Placement.id)).label("placements"),
               func.coalesce(func.sum(Invoice.fee_amount), 0).label("billed_fees"))
        .outerjoin(Invoice, (Invoice.placement_id == Placement.id) &
                   (Invoice.credit_note_of.is_(None)) & (Invoice.deleted_at.is_(None)))
        .where(Placement.tenant_id == _tid(ctx), Placement.deleted_at.is_(None))
        .group_by(Placement.recruiter_id)).all()
    return [{"recruiter_id": str(r.recruiter_id) if r.recruiter_id else None,
             "placements": r.placements, "billed_fees": float(r.billed_fees)} for r in rows]


@router.post("/invoices/{invoice_id}/credit-note")
def create_credit_note(invoice_id: uuid.UUID,
                       ctx: RequestContext = Depends(get_current_context),
                       db: Session = Depends(get_db),
                       idempotency_key: str | None = Header(default=None)):
    """Credit-note STRUCTURE against an original invoice (refund-due case after a
    breach). Negative fee mirror of the original; GST math stays inert (C.3)."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    orig = db.execute(select(Invoice).where(Invoice.id == invoice_id,
                                            Invoice.tenant_id == _tid(ctx),
                                            Invoice.deleted_at.is_(None))).scalar_one_or_none()
    if orig is None:
        raise _err(404, "NOT_FOUND", "Invoice not found")
    if orig.credit_note_of is not None:
        raise _err(409, "IS_CREDIT_NOTE", "Cannot credit-note a credit note")
    existing = db.execute(select(Invoice).where(Invoice.credit_note_of == orig.id,
                                                Invoice.deleted_at.is_(None))).scalar_one_or_none()
    if existing is not None:
        raise _err(409, "CREDIT_NOTE_EXISTS", "A credit note already exists for this invoice")
    cn = Invoice(tenant_id=_tid(ctx), business_unit_id=BU, application_id=orig.application_id,
                 client_id=orig.client_id, placement_id=orig.placement_id,
                 base_amount=orig.base_amount, fee_percent=orig.fee_percent,
                 fee_amount=-float(orig.fee_amount or 0),
                 total_amount=-float(orig.total_amount or 0),
                 status="draft", credit_note_of=orig.id)
    db.add(cn)
    db.flush()
    # B.13 no-double-count: crediting the fee auto-voids an accrued vendor
    # commission on the same placement (paid commissions need explicit handling).
    if orig.placement_id is not None:
        from ..models_staffing import VendorCommission
        vc = db.execute(select(VendorCommission).where(
            VendorCommission.placement_id == orig.placement_id,
            VendorCommission.status == "accrued",
            VendorCommission.deleted_at.is_(None))).scalar_one_or_none()
        if vc is not None:
            vc.status = "void"
            vc.void_reason = f"fee credit-noted (invoice {orig.id})"
            write_audit(db, ctx, "vendor.commission_void", "vendor_commission", vc.id,
                        after={"reason": vc.void_reason, "auto": True})
    write_audit(db, ctx, "invoice.credit_note", "invoice", cn.id,
                after={"credit_note_of": str(orig.id), "amount": float(cn.total_amount)})
    db.commit()
    res = {"id": str(cn.id), "credit_note_of": str(orig.id),
           "total_amount": float(cn.total_amount), "status": cn.status}
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/invoices/overdue")
def overdue_invoices(ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db)):
    """Dunning DETECTION (delivery stubbed until B.10/SES) — tenant-scoped view of
    what dunning_sweep() computes."""
    _require_staff(ctx)
    return [r for r in dunning_sweep(db)
            if db.get(Invoice, uuid.UUID(r["invoice_id"])).tenant_id == _tid(ctx)]


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf_download(invoice_id: uuid.UUID,
                         ctx: RequestContext = Depends(get_current_context),
                         db: Session = Depends(get_db)):
    """Render the invoice PDF (fee line + pending GST/TDS lines), store to S3 under
    the tenant prefix, return a pre-signed GET. Numbering is PROVISIONAL (C.3)."""
    _require_staff(ctx)
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id,
                                           Invoice.tenant_id == _tid(ctx),
                                           Invoice.deleted_at.is_(None))).scalar_one_or_none()
    if inv is None:
        raise _err(404, "NOT_FOUND", "Invoice not found")
    appn = db.get(Application, inv.application_id)
    cand = db.get(Candidate, appn.candidate_id) if appn else None
    job = db.get(Job, appn.job_id) if appn else None
    client = db.get(Client, inv.client_id) if inv.client_id else None
    plc = db.get(Placement, inv.placement_id) if inv.placement_id else None
    pdf = invoice_pdf.build_invoice_pdf(
        invoice=inv, client_name=client.name if client else "—",
        candidate_name=cand.full_name if cand else "—",
        job_title=job.title if job else None,
        joined_on=plc.joined_on if plc else None)
    key = (f"tenant={inv.tenant_id}/business_unit=STAFFING/invoices/{inv.id}/"
           f"{invoice_pdf.provisional_number(inv.id)}.pdf")
    storage._client().put_object(Bucket=storage.settings.storage_bucket, Key=key,
                                 Body=pdf, ContentType="application/pdf")
    write_audit(db, ctx, "invoice.pdf_render", "invoice", inv.id, after={"s3_key": key})
    db.commit()
    return {"download_url": storage.presign_get(key), "s3_key": key,
            "number": invoice_pdf.provisional_number(inv.id),
            "expires_in": storage.PRESIGN_GET_TTL}
