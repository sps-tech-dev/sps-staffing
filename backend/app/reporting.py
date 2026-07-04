"""Founder-dashboard read-models (B.11) — on-read aggregation + Redis cache.

SETTLED DECISIONS (STOP-1):
  A. v1 = on-read aggregation + Redis cache (NOT nightly materialized tables —
     that's the volume scale-up, tracked in PENDING, added behind these same
     functions). NO new tables: this is a NO-MIGRATION slice.
  B. REDIS HOLDS AGGREGATES ONLY — enforced STRUCTURALLY by cache_guard(): every
     leaf of a cached payload must be a number/bool/None, or a string that is a
     known label (pipeline stages, BU codes, statuses, metric names, template
     codes) or a date bucket (YYYY-MM / YYYY-MM-DD). Anything else — names,
     emails, free text — raises CacheGuardError BEFORE the value can reach
     Redis. This is the PENDING B4 (no-PII-in-Redis) invariant by construction.
  C. Key = dash:founder:<tenant>:<bu|all>:<metric>:<range>; TTL 300s;
     ?refresh=1 deletes the key and recomputes.

All aggregation inputs are tenant-scoped; nothing here can aggregate across
tenants (the tenant_id is baked into every query AND the cache key).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import uuid as _uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .db import get_redis
from .jobs import derived_guarantee_state
from .models import Notification
from .models_staffing import (
    APPLICATION_STAGES, Application, Candidate, Invoice, Job, Placement, Test,
)
from .pipeline import ACTIVE_STAGES

log = logging.getLogger("sps.reporting")

CACHE_TTL_SECONDS = 300
_DATE_BUCKET = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")

# The complete set of string labels a founder-cache value may contain.
ALLOWED_LABELS = frozenset(
    set(APPLICATION_STAGES)
    | {"STAFFING", "ACADEMY", "CONSULTING", "all"}
    | {"pending", "sent", "failed", "skipped"}                     # notification statuses
    | {"active", "in_guarantee", "cleared", "breached", "replaced"}  # placement states
    | {"draft", "issued", "paid", "cancelled"}                     # invoice statuses
    | {"assessment_result", "interview_reminder", "invoice_dunning"}
    | {"revenue", "placements", "applications"}                    # trend metric names
)


# Field names the payloads are allowed to use as dict KEYS (programmer-defined
# literals — enumerated, not pattern-matched, so nothing can be smuggled).
ALLOWED_FIELDS = frozenset({
    "revenue_mtd", "fees_billed_total", "open_jobs", "candidates_total",
    "placements_total", "placements_in_guarantee", "pipeline_active",
    "pipeline_funnel", "assessment_pass_rate", "notifications",
    "metric", "series", "jobs", "applications", "placements", "fees_billed",
})


class CacheGuardError(ValueError):
    """A non-aggregate (potential PII) value tried to reach a founder cache key."""


def cache_guard(value, _path="$", _is_key=False):
    """Recursively assert a payload is PII-free-by-construction (decision B).
    KEYS may be enumerated field names, known labels, or date buckets; VALUES may
    only be numbers/bools/None, known labels, or date buckets — free text, names
    and emails are structurally unreachable."""
    if value is None or isinstance(value, (int, float, bool)):
        return
    if isinstance(value, str):
        if value in ALLOWED_LABELS or _DATE_BUCKET.match(value):
            return
        if _is_key and value in ALLOWED_FIELDS:
            return
        raise CacheGuardError(f"non-aggregate string at {_path}: {value!r}")
    if isinstance(value, dict):
        for k, v in value.items():
            cache_guard(k, f"{_path}.{k}", _is_key=True)
            cache_guard(v, f"{_path}.{k}")
        return
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            cache_guard(v, f"{_path}[{i}]")
        return
    raise CacheGuardError(f"uncacheable type at {_path}: {type(value).__name__}")


def cache_key(tenant_id, bu: str, metric: str, range_: str) -> str:
    return f"dash:founder:{tenant_id}:{bu}:{metric}:{range_}"


def get_or_compute(key: str, compute, *, refresh: bool = False, ttl: int = CACHE_TTL_SECONDS):
    """Redis get-or-compute. The guard runs on EVERY write path — a PII value can
    never be cached. Redis unavailability degrades to compute (never fails reads)."""
    r = None
    try:
        r = get_redis()
        if refresh:
            r.delete(key)
        else:
            raw = r.get(key)
            if raw:
                return json.loads(raw)
    except Exception:  # noqa: BLE001 — cache is an optimization, never a dependency
        r = None
    value = compute()
    cache_guard(value)                      # structural PII gate BEFORE any write
    if r is not None:
        try:
            r.set(key, json.dumps(value), ex=ttl)
        except Exception:  # noqa: BLE001
            pass
    return value


# ── aggregations (all tenant-scoped, PII-free by shape) ──────────
def _tid(tenant_id) -> _uuid.UUID:
    return _uuid.UUID(str(tenant_id))


def _month_floor(d: dt.date) -> dt.date:
    return d.replace(day=1)


def overview(db: Session, tenant_id) -> dict:
    tid = _tid(tenant_id)
    today = dt.datetime.now(dt.timezone.utc).date()
    month_start = _month_floor(today)

    revenue_mtd = float(db.execute(select(func.coalesce(func.sum(Invoice.fee_amount), 0)).where(
        Invoice.tenant_id == tid, Invoice.deleted_at.is_(None),
        Invoice.created_at >= month_start)).scalar_one())
    fees_total = float(db.execute(select(func.coalesce(func.sum(Invoice.fee_amount), 0)).where(
        Invoice.tenant_id == tid, Invoice.deleted_at.is_(None))).scalar_one())
    open_jobs = db.execute(select(func.count()).select_from(Job).where(
        Job.tenant_id == tid, Job.status == "open", Job.deleted_at.is_(None))).scalar_one()
    candidates = db.execute(select(func.count()).select_from(Candidate).where(
        Candidate.tenant_id == tid, Candidate.deleted_at.is_(None))).scalar_one()
    placements = db.execute(select(Placement).where(
        Placement.tenant_id == tid, Placement.deleted_at.is_(None))).scalars().all()
    in_guarantee = sum(1 for p in placements if derived_guarantee_state(p) == "in_guarantee")
    pipeline_active = db.execute(select(func.count()).select_from(Application).where(
        Application.tenant_id == tid, Application.deleted_at.is_(None),
        Application.stage.in_(ACTIVE_STAGES))).scalar_one()
    funnel_rows = db.execute(select(Application.stage, func.count()).where(
        Application.tenant_id == tid, Application.deleted_at.is_(None))
        .group_by(Application.stage)).all()
    funnel = {stage: 0 for stage in APPLICATION_STAGES}
    funnel.update({r[0]: r[1] for r in funnel_rows})
    graded = db.execute(select(
        func.count(), func.coalesce(func.sum(case((Test.passed.is_(True), 1), else_=0)), 0)).where(
        Test.tenant_id == tid, Test.status == "submitted", Test.score.isnot(None),
        Test.deleted_at.is_(None))).one()
    pass_rate = round(graded[1] / graded[0], 4) if graded[0] else None
    notif_rows = db.execute(select(Notification.status, func.count()).where(
        Notification.tenant_id == tid).group_by(Notification.status)).all()
    notif = {s: 0 for s in ("pending", "sent", "failed", "skipped")}
    notif.update({r[0]: r[1] for r in notif_rows})

    return {"revenue_mtd": revenue_mtd, "fees_billed_total": fees_total,
            "open_jobs": open_jobs, "candidates_total": candidates,
            "placements_total": len(placements), "placements_in_guarantee": in_guarantee,
            "pipeline_active": pipeline_active, "pipeline_funnel": funnel,
            "assessment_pass_rate": pass_rate, "notifications": notif}


TREND_METRICS = ("revenue", "placements", "applications")


def trends(db: Session, tenant_id, metric: str, months: int) -> dict:
    tid = _tid(tenant_id)
    today = dt.datetime.now(dt.timezone.utc).date()
    buckets = []
    cursor = _month_floor(today)
    for _ in range(months):
        buckets.append(cursor)
        cursor = _month_floor(cursor - dt.timedelta(days=1))
    buckets.reverse()
    series = {}
    for start in buckets:
        end = (start + dt.timedelta(days=32)).replace(day=1)
        label = start.strftime("%Y-%m")
        if metric == "revenue":
            v = float(db.execute(select(func.coalesce(func.sum(Invoice.fee_amount), 0)).where(
                Invoice.tenant_id == tid, Invoice.deleted_at.is_(None),
                Invoice.created_at >= start, Invoice.created_at < end)).scalar_one())
        elif metric == "placements":
            v = db.execute(select(func.count()).select_from(Placement).where(
                Placement.tenant_id == tid, Placement.deleted_at.is_(None),
                Placement.joined_on >= start, Placement.joined_on < end)).scalar_one()
        else:  # applications
            v = db.execute(select(func.count()).select_from(Application).where(
                Application.tenant_id == tid, Application.deleted_at.is_(None),
                Application.created_at >= start, Application.created_at < end)).scalar_one()
        series[label] = v
    return {"metric": metric, "series": series}


def by_bu(db: Session, tenant_id) -> dict:
    """Per-BU columns. ACADEMY/CONSULTING are computed with the SAME queries and
    are naturally zero until those verticals exist — present-but-zero, not faked."""
    tid = _tid(tenant_id)
    out = {}
    for bu in ("STAFFING", "ACADEMY", "CONSULTING"):
        jobs = db.execute(select(func.count()).select_from(Job).where(
            Job.tenant_id == tid, Job.business_unit_id == bu,
            Job.deleted_at.is_(None))).scalar_one()
        apps = db.execute(select(func.count()).select_from(Application).where(
            Application.tenant_id == tid, Application.business_unit_id == bu,
            Application.deleted_at.is_(None))).scalar_one()
        plc = db.execute(select(func.count()).select_from(Placement).where(
            Placement.tenant_id == tid, Placement.business_unit_id == bu,
            Placement.deleted_at.is_(None))).scalar_one()
        fees = float(db.execute(select(func.coalesce(func.sum(Invoice.fee_amount), 0)).where(
            Invoice.tenant_id == tid, Invoice.business_unit_id == bu,
            Invoice.deleted_at.is_(None))).scalar_one())
        out[bu] = {"jobs": jobs, "applications": apps, "placements": plc,
                   "fees_billed": fees}
    return out
