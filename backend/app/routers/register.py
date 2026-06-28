"""Public candidate self-registration — secure intake (Part 6 / Part 10 / Part 19).

UNAUTHENTICATED endpoint. Layered gates, in order:
  1. hCaptcha bot gate (verify_captcha).
  2. DPDP consent gate — PAN/phone are NOT collected without recorded consent.
  3. Tenant resolved from the Host (subdomain → tenant; apex/localhost → owner).
  4. Candidate persisted with PII encrypted (EncryptedStr) + blind index; a
     duplicate phone/PAN (Part 19) → 409.
  5. Consent recorded in the F6 ledger against the new CANDIDATE (subject_candidate_id).

STOP-3: the consent NOTICE wording is stubbed ([LEGAL COPY TBD], from privacy.py).
STOP-4: real hCaptcha keys (account); local/test mode passes a present token.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..captcha import verify_captcha
from ..config import settings
from ..context import RequestContext, tenant_from_host
from ..crypto import blind_index
from ..db import get_db
from ..idempotency import get_cached, store
from ..models import ClientRegistrationRequest, Consent, Tenant
from ..models_staffing import Candidate
from ..validation import normalize_phone, validate_email, validate_name, validate_pan
from .privacy import POLICY_TEXT, POLICY_VERSION

router = APIRouter()


class RegistrationIn(BaseModel):
    full_name: str
    email: str
    phone: str
    pan: str
    skills: list[str] | None = None
    total_exp: float | None = None
    captcha_token: str | None = None
    consent_data_processing: bool = False
    consent_marketing: bool = False

    @field_validator("full_name")
    @classmethod
    def _fn(cls, v): return validate_name(v)

    @field_validator("email")
    @classmethod
    def _e(cls, v): return validate_email(v)

    @field_validator("phone")
    @classmethod
    def _p(cls, v): return normalize_phone(v)

    @field_validator("pan")
    @classmethod
    def _pan(cls, v): return validate_pan(v)


def _dup(db):
    db.rollback()
    raise HTTPException(status_code=409, detail={
        "code": "DUPLICATE_CANDIDATE",
        "message": "A candidate with this phone or PAN is already registered",
    })


@router.get("/config")
def registration_config():
    """Public config for the registration page: captcha sitekey + (stubbed) consent
    notices to render at the point of collection."""
    return {
        "hcaptcha_sitekey": settings.hcaptcha_sitekey,
        "policy_version": POLICY_VERSION,
        "notices": {k: POLICY_TEXT[k] for k in ("data_processing", "marketing")},
    }


@router.post("/candidate")
def register_candidate(body: RegistrationIn, request: Request, db: Session = Depends(get_db),
                       idempotency_key: str | None = Header(default=None)):
    # 1) bot gate
    if not verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail={
            "code": "CAPTCHA_FAILED", "message": "Captcha verification failed — please retry"})

    # 2) consent gate — cannot collect PAN without recorded consent
    if not body.consent_data_processing:
        raise HTTPException(status_code=422, detail={
            "code": "CONSENT_REQUIRED",
            "message": "Consent to data processing is required to register"})

    # 3) resolve tenant from the Host (public: no JWT). apex/localhost → owner.
    slug = tenant_from_host(request.headers.get("host", ""), settings.app_base_domain)
    tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail={
            "code": "UNKNOWN_TENANT", "message": "Unknown registration site"})

    if (cached := get_cached(str(tenant.id), idempotency_key)):
        return cached

    # 4) create candidate with PII encrypted + blind index (dedup → 409)
    cand = Candidate(
        tenant_id=tenant.id, full_name=body.full_name, email=body.email,
        phone_enc=body.phone, pan_enc=body.pan,
        phone_bidx=blind_index(body.phone), pan_bidx=blind_index(body.pan),
        skills=body.skills, total_exp=body.total_exp, source="self_registration",
    )
    db.add(cand)
    try:
        db.flush()
    except IntegrityError:
        _dup(db)

    # 5) record consent in the F6 ledger against the candidate
    db.add(Consent(tenant_id=tenant.id, subject_candidate_id=cand.id,
                   purpose="data_processing", granted=True, policy_version=POLICY_VERSION))
    if body.consent_marketing:
        db.add(Consent(tenant_id=tenant.id, subject_candidate_id=cand.id,
                       purpose="marketing", granted=True, policy_version=POLICY_VERSION))

    ctx = RequestContext(tenant_id=str(tenant.id), business_unit_id="STAFFING", user_id=None)
    write_audit(db, ctx, "candidate.register", "candidate", cand.id)
    try:
        db.commit()
    except IntegrityError:
        _dup(db)

    res = {"id": str(cand.id), "status": "registered", "policy_version": POLICY_VERSION}
    store(str(tenant.id), idempotency_key, res)
    return res


# ── public CLIENT self-registration (Task 2) ─────────────────────
class ClientRegistrationIn(BaseModel):
    company_name: str
    industry: str | None = None
    contact_person: str
    email: str
    phone: str
    website: str | None = None
    company_size: str | None = None
    captcha_token: str | None = None
    consent_data_processing: bool = False

    @field_validator("company_name", "contact_person")
    @classmethod
    def _req(cls, v):
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("This field is required (min 2 characters)")
        return v

    @field_validator("contact_person")
    @classmethod
    def _name(cls, v):
        return validate_name(v)

    @field_validator("email")
    @classmethod
    def _e(cls, v):
        return validate_email(v)

    @field_validator("phone")
    @classmethod
    def _p(cls, v):
        return normalize_phone(v)


@router.post("/client")
def register_client(body: ClientRegistrationIn, request: Request, db: Session = Depends(get_db),
                    idempotency_key: str | None = Header(default=None)):
    """Public client self-registration → a PENDING, UNLINKED request. Grants NOTHING
    until an admin approves + links it to a clients row (the security gate). Contact
    phone is encrypted at rest (personal data); consent + captcha gated like candidate reg."""
    if not verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail={
            "code": "CAPTCHA_FAILED", "message": "Captcha verification failed — please retry"})
    if not body.consent_data_processing:
        raise HTTPException(status_code=422, detail={
            "code": "CONSENT_REQUIRED", "message": "Consent to data processing is required to register"})
    slug = tenant_from_host(request.headers.get("host", ""), settings.app_base_domain)
    tenant = db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail={"code": "UNKNOWN_TENANT", "message": "Unknown registration site"})

    if (cached := get_cached(str(tenant.id), idempotency_key)):
        return cached

    req = ClientRegistrationRequest(
        tenant_id=tenant.id, company_name=body.company_name, industry=body.industry,
        contact_person=body.contact_person, email=body.email,
        phone_enc=body.phone, phone_bidx=blind_index(body.phone),
        website=body.website, company_size=body.company_size,
        consent_data_processing=True, policy_version=POLICY_VERSION, status="pending")
    db.add(req)
    db.flush()
    ctx = RequestContext(tenant_id=str(tenant.id), business_unit_id="STAFFING", user_id=None)
    write_audit(db, ctx, "client.register", "client_registration_request", req.id,
                after={"company": body.company_name})
    db.commit()
    res = {"id": str(req.id), "status": "pending", "policy_version": POLICY_VERSION}
    store(str(tenant.id), idempotency_key, res)
    return res
