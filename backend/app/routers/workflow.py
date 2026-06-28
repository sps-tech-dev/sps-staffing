"""Staffing workflow endpoints (Part 5): submissions (+ offers / interviews /
invoices / vendors in later slices). Two-axis scoped, staff-gated, idempotent."""
from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from ..idempotency import get_cached, store
from ..models_staffing import (
    DEFAULT_FEE_PERCENT, INTERVIEW_MODES, INTERVIEW_STATUSES, INVOICE_STATUSES,
    OFFER_STATUSES, SUBMISSION_STATUSES, VENDOR_STATUSES, VENDOR_SUB_STATUSES,
    Application, Candidate, Interview, Invoice, Job, Offer, Submission, Vendor, VendorSubmission,
)
from .staffing import BU, _require_staff, _tid


def _now():
    return datetime.datetime.now(datetime.timezone.utc)

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────
def _app_or_404(db: Session, ctx: RequestContext, app_id: uuid.UUID) -> Application:
    a = db.execute(select(Application).where(
        Application.id == app_id, Application.tenant_id == _tid(ctx),
        Application.business_unit_id == BU, Application.deleted_at.is_(None))).scalar_one_or_none()
    if a is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Application not found"})
    return a


def _sub_dict(s: Submission) -> dict:
    return {"id": str(s.id), "application_id": str(s.application_id), "status": s.status,
            "client_feedback": s.client_feedback,
            "created_at": s.created_at.isoformat() if s.created_at else None}


# ── submissions ──────────────────────────────────────────────────
class FeedbackIn(BaseModel):
    status: str | None = None
    client_feedback: str | None = None

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v is not None and v not in SUBMISSION_STATUSES:
            raise ValueError(f"status must be one of {SUBMISSION_STATUSES}")
        return v


@router.post("/applications/{app_id}/submissions")
def create_submission(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                      db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Submit a candidate/application to the client."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    _app_or_404(db, ctx, app_id)  # tenant+BU ownership check
    obj = Submission(tenant_id=_tid(ctx), business_unit_id=BU, application_id=app_id,
                     status="submitted", submitted_by=uuid.UUID(str(ctx.user_id)) if ctx.user_id else None)
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "submission.create", "submission", obj.id, after={"application_id": str(app_id)})
    db.commit()
    res = _sub_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/applications/{app_id}/submissions")
def list_app_submissions(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                         db: Session = Depends(get_db)):
    _require_staff(ctx)
    _app_or_404(db, ctx, app_id)
    rows = db.execute(select(Submission).where(
        Submission.tenant_id == _tid(ctx), Submission.business_unit_id == BU,
        Submission.application_id == app_id, Submission.deleted_at.is_(None))
        .order_by(Submission.created_at.desc())).scalars().all()
    return [_sub_dict(s) for s in rows]


@router.get("/submissions")
def list_submissions(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Submissions dashboard — tenant+BU scoped, with candidate + job names."""
    _require_staff(ctx)
    rows = db.execute(
        select(Submission, Candidate.full_name, Job.title)
        .join(Application, Application.id == Submission.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Submission.tenant_id == _tid(ctx), Submission.business_unit_id == BU,
               Submission.deleted_at.is_(None))
        .order_by(Submission.created_at.desc())
    ).all()
    return [{**_sub_dict(s), "candidate": name, "job": title} for s, name, title in rows]


@router.patch("/submissions/{submission_id}")
def update_submission(submission_id: uuid.UUID, body: FeedbackIn,
                      ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Record client feedback / status (under_review / shortlisted / rejected)."""
    _require_staff(ctx)
    s = db.execute(select(Submission).where(
        Submission.id == submission_id, Submission.tenant_id == _tid(ctx),
        Submission.business_unit_id == BU, Submission.deleted_at.is_(None))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Submission not found"})
    before = {"status": s.status}
    if body.status is not None:
        s.status = body.status
    if body.client_feedback is not None:
        s.client_feedback = body.client_feedback
    db.flush()
    write_audit(db, ctx, "submission.update", "submission", s.id, before=before,
                after={"status": s.status})
    db.commit()
    return _sub_dict(s)


# ── offers ───────────────────────────────────────────────────────
class OfferIn(BaseModel):
    ctc: float | None = None
    joining_date: datetime.date | None = None


class OfferUpdateIn(BaseModel):
    status: str | None = None
    ctc: float | None = None
    joining_date: datetime.date | None = None
    rtr_signed: bool | None = None

    @field_validator("status")
    @classmethod
    def _st(cls, v):
        if v is not None and v not in OFFER_STATUSES:
            raise ValueError(f"status must be one of {OFFER_STATUSES}")
        return v


def _offer_dict(o: Offer) -> dict:
    return {"id": str(o.id), "application_id": str(o.application_id),
            "ctc": float(o.ctc) if o.ctc is not None else None,
            "joining_date": o.joining_date.isoformat() if o.joining_date else None,
            "status": o.status,
            "rtr_signed_at": o.rtr_signed_at.isoformat() if o.rtr_signed_at else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
            "created_at": o.created_at.isoformat() if o.created_at else None}


@router.post("/applications/{app_id}/offers")
def create_offer(app_id: uuid.UUID, body: OfferIn, ctx: RequestContext = Depends(get_current_context),
                 db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Create an offer (draft) for an application."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    _app_or_404(db, ctx, app_id)
    obj = Offer(tenant_id=_tid(ctx), business_unit_id=BU, application_id=app_id,
                ctc=body.ctc, joining_date=body.joining_date, status="draft")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "offer.create", "offer", obj.id, after={"application_id": str(app_id)})
    db.commit()
    res = _offer_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/applications/{app_id}/offers")
def list_app_offers(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                    db: Session = Depends(get_db)):
    _require_staff(ctx)
    _app_or_404(db, ctx, app_id)
    rows = db.execute(select(Offer).where(
        Offer.tenant_id == _tid(ctx), Offer.business_unit_id == BU,
        Offer.application_id == app_id, Offer.deleted_at.is_(None))
        .order_by(Offer.created_at.desc())).scalars().all()
    return [_offer_dict(o) for o in rows]


@router.get("/offers")
def list_offers(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Offers dashboard — tenant+BU scoped, with candidate + job names."""
    _require_staff(ctx)
    rows = db.execute(
        select(Offer, Candidate.full_name, Job.title)
        .join(Application, Application.id == Offer.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Offer.tenant_id == _tid(ctx), Offer.business_unit_id == BU, Offer.deleted_at.is_(None))
        .order_by(Offer.created_at.desc())
    ).all()
    return [{**_offer_dict(o), "candidate": name, "job": title} for o, name, title in rows]


@router.patch("/offers/{offer_id}")
def update_offer(offer_id: uuid.UUID, body: OfferUpdateIn,
                 ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Update offer: status, CTC, joining date, RTR-signed / acceptance tracking."""
    _require_staff(ctx)
    o = db.execute(select(Offer).where(
        Offer.id == offer_id, Offer.tenant_id == _tid(ctx),
        Offer.business_unit_id == BU, Offer.deleted_at.is_(None))).scalar_one_or_none()
    if o is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Offer not found"})
    before = {"status": o.status}
    if body.ctc is not None:
        o.ctc = body.ctc
    if body.joining_date is not None:
        o.joining_date = body.joining_date
    if body.rtr_signed:
        o.rtr_signed_at = _now()
    if body.status is not None:
        o.status = body.status
        if body.status == "accepted" and o.accepted_at is None:
            o.accepted_at = _now()
    db.flush()
    write_audit(db, ctx, "offer.update", "offer", o.id, before=before, after={"status": o.status})
    db.commit()
    return _offer_dict(o)


# ── interviews ───────────────────────────────────────────────────
class InterviewIn(BaseModel):
    scheduled_at: datetime.datetime | None = None
    mode: str | None = None
    interviewer_name: str | None = None

    @field_validator("mode")
    @classmethod
    def _m(cls, v):
        if v is not None and v not in INTERVIEW_MODES:
            raise ValueError(f"mode must be one of {INTERVIEW_MODES}")
        return v


class InterviewUpdateIn(BaseModel):
    scheduled_at: datetime.datetime | None = None
    mode: str | None = None
    status: str | None = None
    interviewer_name: str | None = None
    feedback: str | None = None

    @field_validator("mode")
    @classmethod
    def _m(cls, v):
        if v is not None and v not in INTERVIEW_MODES:
            raise ValueError(f"mode must be one of {INTERVIEW_MODES}")
        return v

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in INTERVIEW_STATUSES:
            raise ValueError(f"status must be one of {INTERVIEW_STATUSES}")
        return v


def _iv_dict(i: Interview) -> dict:
    return {"id": str(i.id), "application_id": str(i.application_id),
            "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
            "mode": i.mode, "status": i.status, "interviewer_name": i.interviewer_name,
            "feedback": i.feedback,
            "created_at": i.created_at.isoformat() if i.created_at else None}


@router.post("/applications/{app_id}/interviews")
def create_interview(app_id: uuid.UUID, body: InterviewIn, ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Schedule an interview for an application."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    _app_or_404(db, ctx, app_id)
    obj = Interview(tenant_id=_tid(ctx), business_unit_id=BU, application_id=app_id,
                    scheduled_at=body.scheduled_at, mode=body.mode or "video",
                    interviewer_name=body.interviewer_name, status="scheduled")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "interview.create", "interview", obj.id, after={"application_id": str(app_id)})
    db.commit()
    res = _iv_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/applications/{app_id}/interviews")
def list_app_interviews(app_id: uuid.UUID, ctx: RequestContext = Depends(get_current_context),
                        db: Session = Depends(get_db)):
    _require_staff(ctx)
    _app_or_404(db, ctx, app_id)
    rows = db.execute(select(Interview).where(
        Interview.tenant_id == _tid(ctx), Interview.business_unit_id == BU,
        Interview.application_id == app_id, Interview.deleted_at.is_(None))
        .order_by(Interview.scheduled_at.asc().nulls_last())).scalars().all()
    return [_iv_dict(i) for i in rows]


@router.get("/interviews")
def list_interviews(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Interviews dashboard — tenant+BU scoped, with candidate + job names."""
    _require_staff(ctx)
    rows = db.execute(
        select(Interview, Candidate.full_name, Job.title)
        .join(Application, Application.id == Interview.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Interview.tenant_id == _tid(ctx), Interview.business_unit_id == BU,
               Interview.deleted_at.is_(None))
        .order_by(Interview.scheduled_at.asc().nulls_last())
    ).all()
    return [{**_iv_dict(i), "candidate": name, "job": title} for i, name, title in rows]


@router.patch("/interviews/{interview_id}")
def update_interview(interview_id: uuid.UUID, body: InterviewUpdateIn,
                     ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Reschedule / set mode, interviewer, status (completed/cancelled/no_show), feedback."""
    _require_staff(ctx)
    i = db.execute(select(Interview).where(
        Interview.id == interview_id, Interview.tenant_id == _tid(ctx),
        Interview.business_unit_id == BU, Interview.deleted_at.is_(None))).scalar_one_or_none()
    if i is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Interview not found"})
    before = {"status": i.status}
    if body.scheduled_at is not None:
        i.scheduled_at = body.scheduled_at
    if body.mode is not None:
        i.mode = body.mode
    if body.status is not None:
        i.status = body.status
    if body.interviewer_name is not None:
        i.interviewer_name = body.interviewer_name
    if body.feedback is not None:
        i.feedback = body.feedback
    db.flush()
    write_audit(db, ctx, "interview.update", "interview", i.id, before=before, after={"status": i.status})
    db.commit()
    return _iv_dict(i)


# ── invoices (structure only; tax configurable/stubbed, never hardcoded) ──────
class InvoiceIn(BaseModel):
    application_id: uuid.UUID
    base_amount: float
    fee_percent: float | None = None        # defaults to the 15% SPS placement fee
    gst_percent: float | None = None         # TAX — only applied if a rate is supplied (legal Q1)
    tds_percent: float | None = None         # TAX — only applied if a rate is supplied (legal Q1)


class InvoiceUpdateIn(BaseModel):
    status: str | None = None
    gst_percent: float | None = None
    tds_percent: float | None = None

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in INVOICE_STATUSES:
            raise ValueError(f"status must be one of {INVOICE_STATUSES}")
        return v


def _round2(x):
    return round(float(x), 2)


def _compute_invoice(base: float, fee_pct: float, gst_pct, tds_pct):
    """fee = the SPS placement fee (business term). GST/TDS only computed when a
    rate is explicitly supplied — NEVER assumed (rates await legal, PENDING Q1)."""
    fee = _round2(base * fee_pct / 100)
    gst = _round2(fee * gst_pct / 100) if gst_pct is not None else None
    tds = _round2(fee * tds_pct / 100) if tds_pct is not None else None
    total = _round2(fee + (gst or 0) - (tds or 0))
    return fee, gst, tds, total


def _inv_dict(v: Invoice) -> dict:
    f = lambda x: float(x) if x is not None else None  # noqa: E731
    return {"id": str(v.id), "application_id": str(v.application_id),
            "client_id": str(v.client_id) if v.client_id else None,
            "base_amount": f(v.base_amount), "fee_percent": f(v.fee_percent), "fee_amount": f(v.fee_amount),
            "gst_percent": f(v.gst_percent), "gst_amount": f(v.gst_amount),
            "tds_percent": f(v.tds_percent), "tds_amount": f(v.tds_amount),
            "total_amount": f(v.total_amount), "currency": v.currency, "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None}


@router.post("/invoices")
def create_invoice(body: InvoiceIn, ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    """Create a placement invoice. fee_percent defaults to the 15% SPS fee; GST/TDS
    are applied ONLY if a rate is supplied (no hardcoded tax — see PENDING Q1)."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    app = _app_or_404(db, ctx, body.application_id)
    # derive client from the application's job
    job = db.execute(select(Job).where(Job.id == app.job_id, Job.tenant_id == _tid(ctx))).scalar_one_or_none()
    client_id = job.client_id if job else None
    fee_pct = body.fee_percent if body.fee_percent is not None else DEFAULT_FEE_PERCENT
    fee, gst, tds, total = _compute_invoice(body.base_amount, fee_pct, body.gst_percent, body.tds_percent)
    obj = Invoice(tenant_id=_tid(ctx), business_unit_id=BU, application_id=body.application_id,
                  client_id=client_id, base_amount=body.base_amount, fee_percent=fee_pct, fee_amount=fee,
                  gst_percent=body.gst_percent, gst_amount=gst, tds_percent=body.tds_percent, tds_amount=tds,
                  total_amount=total, status="draft")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "invoice.create", "invoice", obj.id, after={"application_id": str(body.application_id)})
    db.commit()
    res = _inv_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/invoices")
def list_invoices(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Invoices dashboard — tenant+BU scoped, with client + candidate names."""
    _require_staff(ctx)
    rows = db.execute(
        select(Invoice, Candidate.full_name, Job.title)
        .join(Application, Application.id == Invoice.application_id)
        .join(Candidate, Candidate.id == Application.candidate_id)
        .join(Job, Job.id == Application.job_id)
        .where(Invoice.tenant_id == _tid(ctx), Invoice.business_unit_id == BU, Invoice.deleted_at.is_(None))
        .order_by(Invoice.created_at.desc())
    ).all()
    return [{**_inv_dict(v), "candidate": name, "job": title} for v, name, title in rows]


@router.patch("/invoices/{invoice_id}")
def update_invoice(invoice_id: uuid.UUID, body: InvoiceUpdateIn,
                   ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Update invoice status and/or supply GST/TDS rates (recomputes totals). Tax is
    only ever applied from explicitly supplied rates — never assumed."""
    _require_staff(ctx)
    v = db.execute(select(Invoice).where(
        Invoice.id == invoice_id, Invoice.tenant_id == _tid(ctx),
        Invoice.business_unit_id == BU, Invoice.deleted_at.is_(None))).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Invoice not found"})
    before = {"status": v.status}
    if body.gst_percent is not None or body.tds_percent is not None:
        gst_pct = body.gst_percent if body.gst_percent is not None else (float(v.gst_percent) if v.gst_percent is not None else None)
        tds_pct = body.tds_percent if body.tds_percent is not None else (float(v.tds_percent) if v.tds_percent is not None else None)
        fee, gst, tds, total = _compute_invoice(float(v.base_amount), float(v.fee_percent), gst_pct, tds_pct)
        v.gst_percent, v.gst_amount, v.tds_percent, v.tds_amount, v.total_amount = gst_pct, gst, tds_pct, tds, total
    if body.status is not None:
        v.status = body.status
    db.flush()
    write_audit(db, ctx, "invoice.update", "invoice", v.id, before=before, after={"status": v.status})
    db.commit()
    return _inv_dict(v)


# ── vendors + vendor submissions (core; contracts/commissions/performance = follow-up) ──
class VendorIn(BaseModel):
    name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    commission_percent: float | None = None

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("Vendor name is required")
        return v


class VendorUpdateIn(BaseModel):
    status: str | None = None
    commission_percent: float | None = None

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in VENDOR_STATUSES:
            raise ValueError(f"status must be one of {VENDOR_STATUSES}")
        return v


class VendorSubIn(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID | None = None
    notes: str | None = None


class VendorSubUpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v is not None and v not in VENDOR_SUB_STATUSES:
            raise ValueError(f"status must be one of {VENDOR_SUB_STATUSES}")
        return v


def _vendor_dict(v: Vendor) -> dict:
    return {"id": str(v.id), "name": v.name, "contact_email": v.contact_email,
            "contact_phone": v.contact_phone,
            "commission_percent": float(v.commission_percent) if v.commission_percent is not None else None,
            "status": v.status}


def _vsub_dict(s: VendorSubmission) -> dict:
    return {"id": str(s.id), "vendor_id": str(s.vendor_id), "candidate_id": str(s.candidate_id),
            "job_id": str(s.job_id) if s.job_id else None, "status": s.status, "notes": s.notes,
            "created_at": s.created_at.isoformat() if s.created_at else None}


@router.post("/vendors")
def create_vendor(body: VendorIn, ctx: RequestContext = Depends(get_current_context),
                  db: Session = Depends(get_db), idempotency_key: str | None = Header(default=None)):
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    obj = Vendor(tenant_id=_tid(ctx), business_unit_id=BU, name=body.name,
                 contact_email=body.contact_email, contact_phone=body.contact_phone,
                 commission_percent=body.commission_percent, status="active")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "vendor.create", "vendor", obj.id, after={"name": body.name})
    db.commit()
    res = _vendor_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/vendors")
def list_vendors(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_staff(ctx)
    rows = db.execute(select(Vendor).where(
        Vendor.tenant_id == _tid(ctx), Vendor.business_unit_id == BU, Vendor.deleted_at.is_(None))
        .order_by(Vendor.created_at.desc())).scalars().all()
    return [_vendor_dict(v) for v in rows]


@router.patch("/vendors/{vendor_id}")
def update_vendor(vendor_id: uuid.UUID, body: VendorUpdateIn,
                  ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_staff(ctx)
    v = db.execute(select(Vendor).where(
        Vendor.id == vendor_id, Vendor.tenant_id == _tid(ctx),
        Vendor.business_unit_id == BU, Vendor.deleted_at.is_(None))).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Vendor not found"})
    if body.status is not None:
        v.status = body.status
    if body.commission_percent is not None:
        v.commission_percent = body.commission_percent
    db.flush()
    write_audit(db, ctx, "vendor.update", "vendor", v.id, after={"status": v.status})
    db.commit()
    return _vendor_dict(v)


@router.post("/vendors/{vendor_id}/submissions")
def create_vendor_submission(vendor_id: uuid.UUID, body: VendorSubIn,
                             ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db),
                             idempotency_key: str | None = Header(default=None)):
    """Attribute a candidate submission to a vendor."""
    _require_staff(ctx)
    if (c := get_cached(str(ctx.tenant_id), idempotency_key)):
        return c
    vendor = db.execute(select(Vendor).where(
        Vendor.id == vendor_id, Vendor.tenant_id == _tid(ctx),
        Vendor.business_unit_id == BU, Vendor.deleted_at.is_(None))).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Vendor not found"})
    cand = db.execute(select(Candidate).where(
        Candidate.id == body.candidate_id, Candidate.tenant_id == _tid(ctx),
        Candidate.deleted_at.is_(None))).scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Candidate not found"})
    obj = VendorSubmission(tenant_id=_tid(ctx), business_unit_id=BU, vendor_id=vendor_id,
                           candidate_id=body.candidate_id, job_id=body.job_id, notes=body.notes, status="submitted")
    db.add(obj)
    db.flush()
    write_audit(db, ctx, "vendor_submission.create", "vendor_submission", obj.id, after={"vendor_id": str(vendor_id)})
    db.commit()
    res = _vsub_dict(obj)
    store(str(ctx.tenant_id), idempotency_key, res)
    return res


@router.get("/vendor-submissions")
def list_vendor_submissions(ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    """Vendor submissions dashboard — with vendor + candidate names."""
    _require_staff(ctx)
    rows = db.execute(
        select(VendorSubmission, Vendor.name, Candidate.full_name)
        .join(Vendor, Vendor.id == VendorSubmission.vendor_id)
        .join(Candidate, Candidate.id == VendorSubmission.candidate_id)
        .where(VendorSubmission.tenant_id == _tid(ctx), VendorSubmission.business_unit_id == BU,
               VendorSubmission.deleted_at.is_(None))
        .order_by(VendorSubmission.created_at.desc())
    ).all()
    return [{**_vsub_dict(s), "vendor": vname, "candidate": cname} for s, vname, cname in rows]


@router.patch("/vendor-submissions/{sub_id}")
def update_vendor_submission(sub_id: uuid.UUID, body: VendorSubUpdateIn,
                             ctx: RequestContext = Depends(get_current_context), db: Session = Depends(get_db)):
    _require_staff(ctx)
    s = db.execute(select(VendorSubmission).where(
        VendorSubmission.id == sub_id, VendorSubmission.tenant_id == _tid(ctx),
        VendorSubmission.business_unit_id == BU, VendorSubmission.deleted_at.is_(None))).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Vendor submission not found"})
    if body.status is not None:
        s.status = body.status
    if body.notes is not None:
        s.notes = body.notes
    db.flush()
    write_audit(db, ctx, "vendor_submission.update", "vendor_submission", s.id, after={"status": s.status})
    db.commit()
    return _vsub_dict(s)
