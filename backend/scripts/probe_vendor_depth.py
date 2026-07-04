"""One-off B.13 real-op verification on dev RDS — sps_app.

Legs: vendor + contract(8%) + per-CLIENT rate(12%) on real RDS → vendor-sourced
placement → commission resolves to the CLIENT rate (12% of the fee, not the
contract base) → rate change after accrual doesn't retro-alter → replacement
accrues nothing → scorecard reflects it. Self-cleans (timeline rows via master
cleanup if any — the placement endpoint emits Joining events).
"""
from __future__ import annotations

import datetime as dt
import sys

from fastapi import HTTPException
from sqlalchemy import delete, select, text

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Invoice, Job, Offer, Placement,
    Vendor, VendorClientRate, VendorCommission, VendorContract, VendorSubmission,
)
from app.routers.placements import PlacementIn, create_placement
from app.routers.vendor_mgmt import AccrueIn, accrue_commission, scorecard

TAG = "[B.13 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                         user_id=None, roles=("recruiter",))
    ok = False
    try:
        vendor = Vendor(tenant_id=tid, business_unit_id="STAFFING", name=f"Probe Vend {TAG}")
        client = Client(tenant_id=tid, business_unit_id="STAFFING", name=f"Probe VdCl {TAG}")
        db.add_all([vendor, client]); db.flush()
        db.add(VendorContract(tenant_id=tid, business_unit_id="STAFFING", vendor_id=vendor.id,
                              base_commission_percent=8, valid_from=dt.date(2026, 1, 1)))
        db.add(VendorClientRate(tenant_id=tid, business_unit_id="STAFFING", vendor_id=vendor.id,
                                client_id=client.id, commission_percent=12))
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Vd Job {TAG}",
                  client_id=client.id)
        cand = Candidate(tenant_id=tid, full_name=f"Probe Vd Cand {TAG}")
        db.add_all([job, cand]); db.flush()
        db.add(VendorSubmission(tenant_id=tid, business_unit_id="STAFFING",
                                vendor_id=vendor.id, candidate_id=cand.id, job_id=job.id))
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, client_id=client.id, stage="joined")
        db.add(appn); db.flush()
        db.add(Offer(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                     client_id=client.id, ctc=1_000_000, joining_date=dt.date.today(),
                     status="accepted"))
        db.commit()
        plc = create_placement(app_id=appn.id, body=PlacementIn(), ctx=ctx, db=db,
                               idempotency_key=None)
        print(f"1. vendor-sourced placement (fee={plc['fee_amount']}) ✅")

        import uuid as _u
        acc = accrue_commission(placement_id=_u.UUID(plc["id"]), body=AccrueIn(),
                                ctx=ctx, db=db, idempotency_key=None)
        assert acc["resolved_percent"] == 12.0 and acc["source_level"] == "client_rate"
        assert acc["commission_amount"] == round(plc["fee_amount"] * 0.12, 2)
        print("2. commission = fee × 12% CLIENT rate (beats the 8% contract base) ✅")

        rate = db.execute(select(VendorClientRate).where(
            VendorClientRate.vendor_id == vendor.id)).scalar_one()
        rate.commission_percent = 20
        db.commit()
        vc = db.execute(select(VendorCommission).where(
            VendorCommission.placement_id == _u.UUID(plc["id"]))).scalar_one()
        db.refresh(vc)
        assert float(vc.resolved_percent) == 12.0
        print("3. post-accrual rate change does NOT retro-alter the locked row ✅")

        try:
            accrue_commission(placement_id=_u.UUID(plc["id"]), body=AccrueIn(),
                              ctx=ctx, db=db, idempotency_key=None)
            print("duplicate accrual allowed ❌"); return 1
        except HTTPException as e:
            db.rollback()
            assert e.status_code == 409
        print("4. duplicate accrual refused (one commission per placement) ✅")

        sc = scorecard(vendor_id=vendor.id, ctx=ctx, db=db)
        assert sc["placements"] == 1 and sc["commission_accrued"] == acc["commission_amount"]
        print(f"5. scorecard on real RDS: conversion={sc['conversion_rate']}, "
              f"accrued={sc['commission_accrued']} ✅")

        # CROSS-SLICE PROOF (B.13 modifies B.9 behavior): credit-noting a fee that
        # carries an ACCRUED commission auto-voids it in the SAME txn, audited auto:true.
        from app.routers.placements import create_credit_note
        create_credit_note(invoice_id=_u.UUID(plc["invoice_id"]), ctx=ctx, db=db,
                           idempotency_key=None)
        db.refresh(vc)
        assert vc.status == "void" and "credit-noted" in vc.void_reason
        n_auto = db.execute(text(
            "SELECT count(*) FROM shared.audit_logs WHERE tenant_id=:t "
            "AND action='vendor.commission_void' AND (after->>'auto')::bool IS TRUE"),
            {"t": str(tid)}).scalar_one()
        assert n_auto >= 1
        sc2 = scorecard(vendor_id=vendor.id, ctx=ctx, db=db)
        assert sc2["commission_accrued"] == 0
        print("6. CROSS-SLICE: credit-note → commission auto-voided in-txn, "
              "audited auto:true, scorecard accrued→0 ✅")
        ok = True
    finally:
        db.rollback()
        for M in (VendorCommission, VendorClientRate, VendorContract, VendorSubmission):
            db.execute(delete(M).where(M.tenant_id == tid,
                       M.vendor_id.in_(select(Vendor.id).where(
                           Vendor.name.like(f"%{TAG}%")))))
        db.execute(delete(Invoice).where(Invoice.tenant_id == tid,
                   Invoice.client_id.in_(select(Client.id).where(Client.name.like(f"%{TAG}%")))))
        db.execute(delete(Placement).where(Placement.tenant_id == tid,
                   Placement.candidate_id.in_(select(Candidate.id).where(
                       Candidate.full_name.like(f"%{TAG}%")))))
        db.execute(delete(Offer).where(Offer.tenant_id == tid,
                   Offer.client_id.in_(select(Client.id).where(Client.name.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.execute(delete(Client).where(Client.tenant_id == tid, Client.name.like(f"%{TAG}%")))
        db.execute(delete(Vendor).where(Vendor.tenant_id == tid, Vendor.name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("7. probe business rows cleaned (timeline rows left for master cleanup)")
    print("B.13 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
