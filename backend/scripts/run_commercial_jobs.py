"""One-off commercial-jobs runner (B.9) — the repo's established run-once ECS
task pattern (like migrate/bootstrap). Runs the guarantee sweep (materializer —
state stays DERIVABLE on read, so a missed run self-heals) and the dunning sweep
(detection only; delivery stubbed until B.10/SES).

Production wiring: an EventBridge Scheduler rule → ECS RunTask on this command,
daily (small free infra addition — tracked in PENDING; correctness never depends
on it because reads derive the guarantee state from dates).
"""
import sys

from app.db import get_sessionmaker
from app.jobs import dunning_sweep, guarantee_sweep
from app.notify import send_sweep


def main() -> int:
    db = get_sessionmaker()()
    try:
        cleared = guarantee_sweep(db)
        overdue = dunning_sweep(db, enqueue_sends=True)   # B.10: enqueues dunning notices
        sends = send_sweep(db)                            # B.10: dispatch via registered channels
        print(f"guarantee_sweep: cleared={cleared}")
        print(f"dunning_sweep: overdue={len(overdue)} (notices enqueued; email delivery = Part D)")
        print(f"send_sweep: {sends}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
