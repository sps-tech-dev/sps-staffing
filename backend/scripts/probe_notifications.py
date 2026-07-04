"""One-off B.10 real-op verification on dev RDS — BACKEND task def (sps_app).

Legs: enqueue on real RDS (render + idempotent dup) → send sweep via
ConsoleChannel (status=sent) → idempotent re-run (0 re-sends) → an email-channel
row parks pending untouched (Part-D-ready). Self-cleans. Exit != 0 on failure.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import delete, select, text

from app import notify
from app.config import settings
from app.db import get_sessionmaker
from app.models import Notification

TAG = "b10-probe"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    try:
        n_tpl = db.execute(text(
            "SELECT count(*) FROM shared.notification_templates WHERE is_active")).scalar_one()
        assert n_tpl >= 3
        print(f"1. seed templates present on dev RDS ({n_tpl}) ✅")

        key = f"{TAG}:{uuid.uuid4()}"
        row = notify.enqueue(db, template_code="assessment_result",
                             recipient="probe@invalid.test",
                             vars={"candidate_name": "Probe", "job_title": "Probe Role",
                                   "result": "pass"},
                             tenant_id=tid, idempotency_key=key)
        db.commit()
        dup = notify.enqueue(db, template_code="assessment_result",
                             recipient="probe@invalid.test", vars={},
                             tenant_id=tid, idempotency_key=key)
        db.commit()
        assert dup.id == row.id and "Probe Role" in row.rendered_body
        print("2. enqueue rendered + duplicate key is a no-op on real RDS ✅")

        res1 = notify.send_sweep(db)
        db.refresh(row)
        assert row.status == "sent" and row.attempts == 1, (row.status, row.attempts)
        res2 = notify.send_sweep(db)
        db.refresh(row)
        assert row.attempts == 1                       # sent never re-sent
        print(f"3. ConsoleChannel sweep sent once; re-run idempotent ✅ ({res1} → {res2})")

        settings.notify_channel_override = ""          # in-process only
        key2 = f"{TAG}:{uuid.uuid4()}"
        row2 = notify.enqueue(db, template_code="assessment_result",
                              recipient="probe2@invalid.test",
                              vars={}, tenant_id=tid, idempotency_key=key2)
        db.commit()
        settings.notify_channel_override = "console"   # restore
        assert row2.channel_type == "email"
        notify.send_sweep(db)
        db.refresh(row2)
        assert row2.status == "pending" and row2.attempts == 0
        print("4. email-channel row PARKED pending, attempts untouched (Part-D-ready) ✅")
        ok = True
    finally:
        db.rollback()
        db.execute(delete(Notification).where(
            Notification.idempotency_key.like(f"{TAG}:%")))
        db.commit(); db.close()
        print("5. probe rows cleaned up")
    print("B.10 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
