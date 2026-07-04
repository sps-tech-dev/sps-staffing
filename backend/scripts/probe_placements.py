"""One-off B.9 real-op verification on dev RDS + real S3 — BACKEND task def (sps_app).

Legs: (1) placement + client-level fee resolution on real RDS, (2) guarantee state
DERIVABLE with the sweep never run, (3) sweep idempotent (1 flip then 0, single
GuaranteeCompletion), (4) breach → reopen → replacement with NO second invoice,
(5) invoice PDF → REAL S3 PUT → presigned GET → object deleted.
Self-cleans business rows; timeline rows left for master cleanup. Exit != 0 on failure.
"""
from __future__ import annotations

import datetime as dt
import sys

from sqlalchemy import delete, func, select, text

from app import invoice_pdf, storage
from app.context import RequestContext
from app.db import get_sessionmaker
from app.jobs import derived_guarantee_state, guarantee_sweep
from app.models_staffing import (
    Application, Candidate, Client, Invoice, Job, Offer, Placement,
)
from app.routers.placements import (
    BreachIn, PlacementIn, ReplacementIn, create_placement, create_replacement, record_breach,
)

TAG = "[B.9 probe]"


def _mk_joined(db, tid, client, job, name):
    cand = Candidate(tenant_id=tid, full_name=f"{name} {TAG}")
    db.add(cand); db.flush()
    appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, client_id=client.id, stage="joined")
    db.add(appn); db.flush()
    db.add(Offer(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                 client_id=client.id, ctc=1_000_000, joining_date=dt.date.today(),
                 status="accepted"))
    db.commit()
    return appn


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None,
                         roles=("recruiter",))
    pdf_key = None
    ok = False
    try:
        client = Client(tenant_id=tid, business_unit_id="STAFFING",
                        name=f"Probe PlcCo {TAG}", fee_percent=12)
        db.add(client); db.flush()
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Plc Job {TAG}",
                  client_id=client.id)
        db.add(job); db.commit()

        appn = _mk_joined(db, tid, client, job, "Probe Plc Cand A")
        res = create_placement(app_id=appn.id, body=PlacementIn(), ctx=ctx, db=db,
                               idempotency_key=None)
        assert res["fee_percent"] == 12.0 and res["fee_amount"] == 120000.0
        assert res["total_amount"] == 120000.0            # taxes inert
        print("1. placement + CLIENT-level fee (1,000,000 × 12% = 120,000; annual base) ✅")

        p = db.get(Placement, __import__("uuid").UUID(res["id"]))
        p.joined_on = dt.date.today() - dt.timedelta(days=90)
        p.guarantee_until = dt.date.today() - dt.timedelta(days=30)
        db.commit(); db.refresh(p)
        assert p.status == "active" and derived_guarantee_state(p) == "cleared"
        print("2. guarantee DERIVABLE on real RDS (status active, derived cleared, no job run) ✅")

        assert guarantee_sweep(db) == 1
        assert guarantee_sweep(db) == 0
        n_ev = db.execute(text(
            "SELECT count(*) FROM staffing.candidate_timeline WHERE candidate_id=:c "
            "AND event_type='GuaranteeCompletion'"), {"c": str(p.candidate_id)}).scalar_one()
        assert n_ev == 1
        print("3. sweep idempotent (1 then 0) + single GuaranteeCompletion ✅")

        appn2 = _mk_joined(db, tid, client, job, "Probe Plc Cand B")
        res2 = create_placement(app_id=appn2.id, body=PlacementIn(), ctx=ctx, db=db,
                                idempotency_key=None)
        record_breach(placement_id=__import__("uuid").UUID(res2["id"]),
                      body=BreachIn(reason="B.9 probe breach"), ctx=ctx, db=db,
                      idempotency_key=None)
        db.refresh(job)
        assert job.status == "open"
        appn3 = _mk_joined(db, tid, client, job, "Probe Plc Cand C")
        rep = create_replacement(placement_id=__import__("uuid").UUID(res2["id"]),
                                 body=ReplacementIn(application_id=appn3.id), ctx=ctx, db=db,
                                 idempotency_key=None)
        assert rep["fee_exempt"] is True
        n_inv = db.execute(select(func.count()).select_from(Invoice).where(
            Invoice.tenant_id == tid, Invoice.client_id == client.id,
            Invoice.credit_note_of.is_(None))).scalar_one()
        assert n_inv == 2, f"expected 2 fee invoices (A + B originals), got {n_inv}"
        print("4. breach → job reopened → replacement with NO second fee invoice ✅")

        inv = db.get(Invoice, __import__("uuid").UUID(res["invoice_id"]))
        pdf = invoice_pdf.build_invoice_pdf(invoice=inv, client_name=client.name,
                                            candidate_name="Probe", job_title=job.title,
                                            joined_on=p.joined_on)
        assert pdf.startswith(b"%PDF")
        pdf_key = (f"tenant={tid}/business_unit=STAFFING/invoices/{inv.id}/"
                   f"{invoice_pdf.provisional_number(inv.id)}.pdf")
        storage._client().put_object(Bucket=storage.settings.storage_bucket, Key=pdf_key,
                                     Body=pdf, ContentType="application/pdf")
        assert storage.head_object(pdf_key) is not None
        url = storage.presign_get(pdf_key)
        assert url.startswith("http")
        print("5. invoice PDF → REAL S3 PUT + presigned GET ✅")
        ok = True
    finally:
        if pdf_key:
            try:
                storage.delete_object(pdf_key)
                print("6. probe S3 object deleted")
            except Exception as e:  # noqa: BLE001
                print(f"6. S3 cleanup failed: {e}")
        db.rollback()
        db.execute(delete(Invoice).where(Invoice.tenant_id == tid,
                   Invoice.client_id.in_(select(Client.id).where(
                       Client.name.like(f"%{TAG}%")))))
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
        db.commit(); db.close()
        print("7. probe business rows cleaned (timeline rows left for master cleanup)")
    print("B.9 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
