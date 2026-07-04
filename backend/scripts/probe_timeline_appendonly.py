"""One-off B.2 append-only proof on dev RDS — runs on the BACKEND task def (sps_app).

As sps_app: INSERT a clearly-marked sentinel row into staffing.candidate_timeline
(MUST succeed), then UPDATE and DELETE it (MUST both be denied by the bootstrap
REVOKE). Prints the exact permission-denied errors. Exits non-zero unless the
outcome is exactly INSERT-ok + UPDATE-denied + DELETE-denied.

Cleanup is NOT done here (sps_app cannot delete by design) — the sentinel row is
removed afterwards via the MIGRATE task def (master creds), matching the
audit_logs append-only verification precedent.
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import create_engine, text

from app.config import settings

SENTINEL_EVENT = "_probe_appendonly"


def main() -> int:
    eng = create_engine(settings.database_url)
    with eng.connect() as cx:
        who = cx.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        print("FAIL: probe must run as sps_app (backend task def)")
        return 1

    # a. INSERT must succeed
    with eng.begin() as cx:
        row_id = cx.execute(text(
            "INSERT INTO staffing.candidate_timeline "
            "(tenant_id, business_unit_id, candidate_id, event_type, payload) "
            "VALUES (:t, 'STAFFING', :c, :e, "
            "jsonb_build_object('probe', 'B.2 append-only verification', 'ts', now()::text)) "
            "RETURNING id"),
            {"t": str(uuid.uuid4()), "c": str(uuid.uuid4()), "e": SENTINEL_EVENT},
        ).scalar_one()
    print(f"a. INSERT as sps_app OK — sentinel row id={row_id} ✅")

    # b. UPDATE must be denied
    update_denied = delete_denied = False
    try:
        with eng.begin() as cx:
            cx.execute(text("UPDATE staffing.candidate_timeline SET event_type='_tampered' "
                            "WHERE id=:i"), {"i": row_id})
        print("b. UPDATE as sps_app SUCCEEDED — REVOKE NOT IN EFFECT ❌")
    except Exception as e:  # noqa: BLE001
        update_denied = "permission denied" in str(e).lower()
        print(f"b. UPDATE denied ✅ — error: {str(e).splitlines()[0][:160]}")

    # b. DELETE must be denied
    try:
        with eng.begin() as cx:
            cx.execute(text("DELETE FROM staffing.candidate_timeline WHERE id=:i"), {"i": row_id})
        print("b. DELETE as sps_app SUCCEEDED — REVOKE NOT IN EFFECT ❌")
    except Exception as e:  # noqa: BLE001
        delete_denied = "permission denied" in str(e).lower()
        print(f"b. DELETE denied ✅ — error: {str(e).splitlines()[0][:160]}")

    ok = update_denied and delete_denied
    print(f"sentinel row id={row_id} left for master cleanup (event_type={SENTINEL_EVENT})")
    print("B.2 APPEND-ONLY PROBE: " + ("PASS" if ok else "FAIL — REVOKE not effective, STOP"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
