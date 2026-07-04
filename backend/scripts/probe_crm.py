"""One-off B.12 real-op verification on dev RDS — sps_app.

Legs: lead stage walk on real RDS → lost-reason enforced → won→convert creates
a client → double-convert returns the SAME client (idempotency guard) → BU
scoping (a CONSULTING lead is invisible to the STAFFING context). Self-cleans.
"""
from __future__ import annotations

import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import Activity, Lead
from app.models_staffing import Client, Job
from app.routers.crm import (
    ConvertIn, _lead_or_404, convert_lead, transition_lead,
)

TAG = "[B.12 probe]"


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
        lead = Lead(tenant_id=tid, business_unit_id="STAFFING", company=f"Probe BD Co {TAG}")
        db.add(lead); db.commit()
        for st in ("qualified", "proposal", "negotiation", "won"):
            transition_lead(db, ctx, lead, st)
            db.commit()
        db.refresh(lead)
        assert lead.stage == "won"
        print("1. stage walk new→…→won on real RDS ✅")

        lead2 = Lead(tenant_id=tid, business_unit_id="STAFFING", company=f"Probe Lost Co {TAG}")
        db.add(lead2); db.commit()
        try:
            transition_lead(db, ctx, lead2, "lost")
            print("lost without reason was allowed ❌"); return 1
        except HTTPException as e:
            db.rollback()
            assert e.status_code == 422
        transition_lead(db, ctx, lead2, "lost", reason="B.12 probe reason")
        db.commit(); db.refresh(lead2)
        assert lead2.lost_reason == "B.12 probe reason"
        print("2. lost-requires-reason enforced on real RDS ✅")

        res1 = convert_lead(lead_id=lead.id, body=ConvertIn(job_title=f"Probe Intake {TAG}"),
                            ctx=ctx, db=db, idempotency_key=None)
        res2 = convert_lead(lead_id=lead.id, body=ConvertIn(), ctx=ctx, db=db,
                            idempotency_key=None)
        assert res1["client_id"] == res2["client_id"] and res2["already_converted"]
        n = db.execute(select(func.count()).select_from(Client).where(
            Client.tenant_id == tid, Client.name == lead.company)).scalar_one()
        assert n == 1
        print("3. won→convert → client + job intake; double-convert same client (n=1) ✅")

        cons = Lead(tenant_id=tid, business_unit_id="CONSULTING",
                    company=f"Probe Consulting Co {TAG}")
        db.add(cons); db.commit()
        try:
            _lead_or_404(db, ctx, cons.id)             # STAFFING ctx must not see it
            print("BU scoping broken ❌"); return 1
        except HTTPException as e:
            assert e.status_code == 404
        print("4. BU scoping: CONSULTING lead invisible to the STAFFING context ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Activity).where(Activity.tenant_id == tid,
                   Activity.lead_id.in_(select(Lead.id).where(
                       Lead.company.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Client).where(Client.tenant_id == tid,
                                        Client.name.like(f"%{TAG}%")))
        db.execute(delete(Lead).where(Lead.tenant_id == tid,
                                      Lead.company.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("5. probe rows cleaned up")
    print("B.12 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
