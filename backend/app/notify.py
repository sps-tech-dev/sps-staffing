"""Notification service (B.10) — channel-abstracted enqueue + the Part-D seam.

SETTLED DECISIONS (STOP-1):
  A. Transport = the shared.notifications TABLE + a one-off runner sweep (B.9
     pattern). The table is queue, delivery-status, idempotency ledger and audit
     in one store. No Redis queue; a worker is a future scale-up behind this
     same interface.
  B. Channels implement AbstractChannel and self-declare their channel_type; the
     REGISTRY decides what's deliverable. Only ConsoleChannel is registered.
     EmailChannel/SmsChannel/WhatsAppChannel are DECLARED (the Part-D seam) but
     not implemented — enqueued rows for unregistered channel types are PARKED
     pending (untouched by the sweep, attempts not burned) so turning a real
     channel on in Part D just picks them up. Zero call-site changes.
  C. ConsoleChannel renders to the app log only (dev sink) — never a durable
     PII store. The notifications table stores recipient + rendered body; bodies
     may contain names/schedule details (operational data) — keep this table out
     of any cache path (PENDING B4 invariant).

Idempotency: callers pass a STABLE key (e.g. 'assessment_result:<test_id>');
UNIQUE(idempotency_key) makes a duplicate enqueue a no-op returning the existing
row — a retried trigger can never double-enqueue, and the sweep never re-sends a
non-pending row. Consent: kind='marketing' checks the shared.consents ledger
(latest 'marketing' row for the subject) → no consent = status='skipped'
(recorded, not sent). TRANSACTIONAL kinds (results, reminders, dunning) are
operational service messages, not marketing — they do not consult marketing
consent (DPDP treats them under the service's lawful basis, captured at
registration as data_processing consent).
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Consent, Notification, NotificationTemplate

log = logging.getLogger("sps.notify")


# ── channel abstraction (the Part-D seam) ────────────────────────
@dataclass(frozen=True)
class RenderedMessage:
    notification_id: str
    channel_type: str
    recipient: str
    subject: str | None
    body: str


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    error: str | None = None


class AbstractChannel(ABC):
    """A delivery channel. Implementations self-declare `channel_type` and are
    added to CHANNEL_REGISTRY — that registration is the ONLY thing Part D
    changes to go live (plus provider credentials)."""
    channel_type: str

    @abstractmethod
    def send(self, msg: RenderedMessage) -> DeliveryResult: ...


class ConsoleChannel(AbstractChannel):
    """Dev sink: logs the fully-rendered message. Log-only — never persists."""
    channel_type = "console"

    def send(self, msg: RenderedMessage) -> DeliveryResult:
        log.info("CONSOLE DELIVERY → %s | subject=%r | body=%r",
                 msg.recipient, msg.subject, msg.body)
        return DeliveryResult(ok=True)


# Part-D placeholders — DECLARED so the seam is visible; not registered.
class EmailChannel(AbstractChannel):     # Part D: SES (+ .ics attach, METHOD:CANCEL)
    channel_type = "email"

    def send(self, msg: RenderedMessage) -> DeliveryResult:
        raise NotImplementedError("EmailChannel is Part D (SES)")


class SmsChannel(AbstractChannel):       # Part D
    channel_type = "sms"

    def send(self, msg: RenderedMessage) -> DeliveryResult:
        raise NotImplementedError("SmsChannel is Part D")


class WhatsAppChannel(AbstractChannel):  # Part D
    channel_type = "whatsapp"

    def send(self, msg: RenderedMessage) -> DeliveryResult:
        raise NotImplementedError("WhatsAppChannel is Part D")


CHANNEL_REGISTRY: dict[str, AbstractChannel] = {
    ConsoleChannel.channel_type: ConsoleChannel(),
    # Part D: register EmailChannel/SmsChannel/WhatsAppChannel here — parked
    # pending rows for those channel types are then picked up by the next sweep.
}


# ── rendering ────────────────────────────────────────────────────
class _SafeDict(dict):
    def __missing__(self, key):  # missing var renders literally, never crashes
        return "{" + key + "}"


def render(template: NotificationTemplate, vars: dict) -> tuple[str | None, str]:
    safe = _SafeDict({k: str(v) for k, v in (vars or {}).items()})
    subject = template.subject.format_map(safe) if template.subject else None
    return subject, template.body.format_map(safe)


# ── enqueue ──────────────────────────────────────────────────────
def enqueue(db: Session, *, template_code: str, recipient: str, vars: dict,
            tenant_id, business_unit_id: str = "STAFFING",
            idempotency_key: str, kind: str = "txn",
            subject_candidate_id=None) -> Notification | None:
    """Render + write ONE pending notifications row inside the caller's txn.
    Duplicate idempotency_key → no-op returning the existing row. Marketing kind
    without a granted 'marketing' consent → status='skipped' (recorded).
    Returns None only when the template is unknown/inactive (logged, never raises
    — a missing template must not fail the business operation)."""
    existing = db.execute(select(Notification).where(
        Notification.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing is not None:
        return existing
    tpl = db.execute(select(NotificationTemplate).where(
        NotificationTemplate.code == template_code,
        NotificationTemplate.is_active.is_(True))).scalar_one_or_none()
    if tpl is None:
        log.error("notify.enqueue: unknown/inactive template %r — notification dropped",
                  template_code)
        return None

    status = "pending"
    skip_reason = None
    if kind == "marketing":
        latest = db.execute(select(Consent).where(
            Consent.subject_candidate_id == subject_candidate_id,
            Consent.purpose == "marketing")
            .order_by(Consent.created_at.desc())).scalars().first()
        if latest is None or not latest.granted:
            status, skip_reason = "skipped", "no marketing consent"

    channel = settings.notify_channel_override or tpl.channel_type
    subject, body = render(tpl, vars)
    row = Notification(tenant_id=uuid.UUID(str(tenant_id)), business_unit_id=business_unit_id,
                       template_code=template_code, channel_type=channel,
                       recipient=recipient, vars=vars or {},
                       rendered_subject=subject, rendered_body=body,
                       status=status, last_error=skip_reason,
                       idempotency_key=idempotency_key)
    db.add(row)
    db.flush()
    return row


# ── the send sweep (one-off runner; see app/jobs.py wiring) ──────
def send_sweep(db: Session) -> dict:
    """Dispatch pending rows whose channel is REGISTERED. Unregistered channel
    types are parked untouched (no attempts burned) — Part-D-ready. A non-pending
    row is never re-sent (status guard). Failures increment attempts + record
    last_error; at NOTIFY_MAX_ATTEMPTS the row goes 'failed' (recoverable by
    resetting status/attempts deliberately). Backoff between attempts = the
    runner cadence (one attempt per sweep run)."""
    rows = db.execute(select(Notification).where(
        Notification.status == "pending",
        Notification.channel_type.in_(list(CHANNEL_REGISTRY)))
        .order_by(Notification.created_at.asc()).limit(500)).scalars().all()
    sent = failed = 0
    for n in rows:
        channel = CHANNEL_REGISTRY[n.channel_type]
        n.attempts += 1
        try:
            result = channel.send(RenderedMessage(
                notification_id=str(n.id), channel_type=n.channel_type,
                recipient=n.recipient, subject=n.rendered_subject, body=n.rendered_body))
        except Exception as e:  # noqa: BLE001 — a channel bug must not kill the sweep
            result = DeliveryResult(ok=False, error=f"{type(e).__name__}: {e}")
        if result.ok:
            n.status = "sent"
            n.sent_at = dt.datetime.now(dt.timezone.utc)
            n.last_error = None
            sent += 1
        else:
            n.last_error = result.error
            if n.attempts >= settings.notify_max_attempts:
                n.status = "failed"
                failed += 1
    db.commit()
    parked = db.execute(select(Notification).where(
        Notification.status == "pending",
        Notification.channel_type.notin_(list(CHANNEL_REGISTRY)))).scalars().all()
    return {"sent": sent, "failed": failed, "parked_unregistered": len(parked)}
