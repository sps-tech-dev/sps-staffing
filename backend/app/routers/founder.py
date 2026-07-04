"""Founder dashboard (B.11) — the MOST SENSITIVE read surface in the system
(revenue, recruiter performance, delivery health).

Gate: FOUNDER_ROLES = {owner, super_admin, founder} ONLY — 'owner' is the
founder's actual seeded slug (0003); 'founder' is included defensively should
RBAC later mint it; plain 'admin' and all staff/recruiter roles are DELIBERATELY
EXCLUDED (stricter than _require_admin), and a client-portal session
(client_id bound) is always rejected. Recruiter-performance and client-health
numbers therefore never reach the people they describe.

Tenant-scoped like everything else: the tenant_id from the verified JWT is baked
into every aggregation AND every cache key — no cross-tenant totals exist.
EVERY access (including exports) writes an audit row (actor, endpoint/metric,
range, refresh) via write_audit.
"""
from __future__ import annotations

import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import reporting
from ..audit import write_audit
from ..context import RequestContext
from ..db import get_db
from ..deps import get_current_context
from .staffing import _tid

router = APIRouter()

FOUNDER_ROLES = {"owner", "super_admin", "founder"}


def _require_founder(ctx: RequestContext):
    if ctx.client_id is not None or not (set(ctx.roles) & FOUNDER_ROLES):
        raise HTTPException(status_code=403, detail={
            "code": "FORBIDDEN", "message": "Founder role required"})


def _audited(db, ctx, endpoint: str, **details):
    write_audit(db, ctx, "dashboard.founder_access", "dashboard", None,
                after={"endpoint": endpoint, **details})
    db.commit()


@router.get("/overview")
def founder_overview(refresh: int = Query(default=0),
                     ctx: RequestContext = Depends(get_current_context),
                     db: Session = Depends(get_db)):
    _require_founder(ctx)
    key = reporting.cache_key(ctx.tenant_id, "all", "overview", "current")
    data = reporting.get_or_compute(key, lambda: reporting.overview(db, ctx.tenant_id),
                                    refresh=bool(refresh))
    _audited(db, ctx, "overview", refresh=bool(refresh))
    return data


@router.get("/trends")
def founder_trends(metric: str = Query(default="revenue"),
                   range: int = Query(default=6, ge=1, le=24, alias="range"),
                   refresh: int = Query(default=0),
                   ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db)):
    _require_founder(ctx)
    if metric not in reporting.TREND_METRICS:
        raise HTTPException(status_code=422, detail={
            "code": "VALIDATION_ERROR",
            "message": f"metric must be one of {reporting.TREND_METRICS}"})
    key = reporting.cache_key(ctx.tenant_id, "all", f"trend-{metric}", f"{range}m")
    data = reporting.get_or_compute(
        key, lambda: reporting.trends(db, ctx.tenant_id, metric, range),
        refresh=bool(refresh))
    _audited(db, ctx, "trends", metric=metric, range_months=range, refresh=bool(refresh))
    return data


@router.get("/by-bu")
def founder_by_bu(refresh: int = Query(default=0),
                  ctx: RequestContext = Depends(get_current_context),
                  db: Session = Depends(get_db)):
    _require_founder(ctx)
    key = reporting.cache_key(ctx.tenant_id, "all", "by-bu", "current")
    data = reporting.get_or_compute(key, lambda: reporting.by_bu(db, ctx.tenant_id),
                                    refresh=bool(refresh))
    _audited(db, ctx, "by-bu", refresh=bool(refresh))
    return data


@router.get("/export")
def founder_export(format: str = Query(default="pdf"),
                   ctx: RequestContext = Depends(get_current_context),
                   db: Session = Depends(get_db)):
    """PDF/Excel export of the SAME PII-free aggregates (fresh compute). Audited."""
    _require_founder(ctx)
    if format not in ("pdf", "xlsx"):
        raise HTTPException(status_code=422, detail={
            "code": "VALIDATION_ERROR", "message": "format must be pdf or xlsx"})
    data = reporting.overview(db, ctx.tenant_id)
    reporting.cache_guard(data)   # same structural gate for exported payloads
    bu = reporting.by_bu(db, ctx.tenant_id)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")

    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Overview"
        ws.append(["SPS Founder Dashboard", ts])
        for k, v in data.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    ws.append([f"{k}.{sk}", sv])
            else:
                ws.append([k, v])
        ws2 = wb.create_sheet("By BU")
        ws2.append(["bu", "jobs", "applications", "placements", "fees_billed"])
        for code, row in bu.items():
            ws2.append([code, row["jobs"], row["applications"], row["placements"],
                        row["fees_billed"]])
        buf = io.BytesIO()
        wb.save(buf)
        content, media, ext = buf.getvalue(), \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        _, h = A4
        y = h - 25 * mm
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, y, f"SPS Founder Dashboard — {ts}")
        y -= 10 * mm
        c.setFont("Helvetica", 10)
        for k, v in data.items():
            if isinstance(v, dict):
                c.drawString(22 * mm, y, f"{k}:")
                y -= 5 * mm
                for sk, sv in v.items():
                    c.drawString(26 * mm, y, f"{sk}: {sv}")
                    y -= 5 * mm
            else:
                c.drawString(22 * mm, y, f"{k}: {v}")
                y -= 5 * mm
            if y < 25 * mm:
                c.showPage(); y = h - 25 * mm; c.setFont("Helvetica", 10)
        c.showPage(); c.save()
        content, media, ext = buf.getvalue(), "application/pdf", "pdf"

    _audited(db, ctx, "export", format=format)
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition":
                             f'attachment; filename="founder-dashboard.{ext}"'})
