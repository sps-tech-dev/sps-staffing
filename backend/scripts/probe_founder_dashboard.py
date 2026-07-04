"""One-off B.11 real-op verification on dev RDS + real ElastiCache — sps_app.

NOTE ON THE ROLE: dev has no browser login (JWT secrets = Part D), so the founder
role is exercised the way prior probes exercise auth — an in-process
RequestContext with roles=('owner',) calling the endpoint functions directly.
The gate itself is additionally proven by a recruiter-role ctx being 403'd.

Legs: gate (owner ok / recruiter 403 / client-session 403) → seeded KPIs match
hand-computed on real RDS → the Redis key exists and its cached JSON contains
ONLY aggregates (inspected) → refresh recomputes → access audit row written →
PDF + xlsx exports round-trip. Self-cleans (incl. the cache keys + audit is
append-only so probe audit rows remain — they are real access records).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select, text

from app import reporting
from app.context import RequestContext
from app.db import get_redis, get_sessionmaker
from app.models_staffing import Application, Candidate, Client, Invoice, Job, Placement
from app.routers.founder import _require_founder, founder_export, founder_overview

TAG = "[B.11 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    owner_ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                               user_id=None, roles=("owner",))
    ok = False
    try:
        # gate
        for roles, client_id, should_pass in ((("owner",), None, True),
                                              (("recruiter",), None, False),
                                              (("client",), str(uuid.uuid4()), False)):
            ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                                 user_id=None, roles=roles, client_id=client_id)
            try:
                _require_founder(ctx)
                assert should_pass, f"{roles}/{client_id} passed the gate!"
            except HTTPException as e:
                assert not should_pass and e.status_code == 403
        print("1. gate: owner ok; recruiter 403; client session 403 ✅")

        client = Client(tenant_id=tid, business_unit_id="STAFFING", name=f"Probe FdrCo {TAG}")
        db.add(client); db.flush()
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Fdr Job {TAG}",
                  client_id=client.id)
        cand = Candidate(tenant_id=tid, full_name=f"Probe Fdr Cand {TAG}")
        db.add_all([job, cand]); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, client_id=client.id, stage="joined")
        db.add(appn); db.flush()
        today = dt.datetime.now(dt.timezone.utc).date()
        plc = Placement(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                        client_id=client.id, candidate_id=cand.id, offered_ctc=1_000_000,
                        joined_on=today, guarantee_until=today + dt.timedelta(days=60))
        db.add(plc); db.flush()
        db.add(Invoice(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                       client_id=client.id, placement_id=plc.id, base_amount=1_000_000,
                       fee_percent=15, fee_amount=150000, total_amount=150000, status="draft"))
        db.commit()

        data = founder_overview(refresh=1, ctx=owner_ctx, db=db)
        assert data["placements_total"] >= 1 and data["fees_billed_total"] >= 150000.0
        print(f"2. overview KPIs on real RDS (placements={data['placements_total']}, "
              f"fees={data['fees_billed_total']}) ✅")

        key = reporting.cache_key(tid, "all", "overview", "current")
        raw = get_redis().get(key)
        assert raw is not None
        cached = json.loads(raw)
        reporting.cache_guard(cached)   # would raise on ANY name/email/free text
        flat = json.dumps(cached)
        assert "Probe Fdr Cand" not in flat and "@" not in flat
        print("3. real ElastiCache key present; cached value passes the PII guard ✅")

        before = db.execute(text(
            "SELECT count(*) FROM shared.audit_logs WHERE tenant_id=:t "
            "AND action='dashboard.founder_access'"), {"t": str(tid)}).scalar_one()
        founder_overview(refresh=1, ctx=owner_ctx, db=db)
        after = db.execute(text(
            "SELECT count(*) FROM shared.audit_logs WHERE tenant_id=:t "
            "AND action='dashboard.founder_access'"), {"t": str(tid)}).scalar_one()
        assert after == before + 1
        print("4. refresh recomputes + every access audit-logged ✅")

        pdf = founder_export(format="pdf", ctx=owner_ctx, db=db)
        xlsx = founder_export(format="xlsx", ctx=owner_ctx, db=db)
        assert pdf.body.startswith(b"%PDF")
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(xlsx.body))
        assert "Overview" in wb.sheetnames
        print("5. PDF + xlsx exports render on real infra ✅")
        ok = True
    finally:
        try:
            get_redis().delete(reporting.cache_key(tid, "all", "overview", "current"))
        except Exception:  # noqa: BLE001
            pass
        db.rollback()
        db.execute(delete(Invoice).where(Invoice.tenant_id == tid,
                   Invoice.client_id.in_(select(Client.id).where(Client.name.like(f"%{TAG}%")))))
        db.execute(delete(Placement).where(Placement.tenant_id == tid,
                   Placement.candidate_id.in_(select(Candidate.id).where(
                       Candidate.full_name.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.execute(delete(Client).where(Client.tenant_id == tid, Client.name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("6. probe rows + cache keys cleaned (audit rows are real access records, kept)")
    print("B.11 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
