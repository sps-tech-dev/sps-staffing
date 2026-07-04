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


def main() -> int:
    db = get_sessionmaker()()
    try:
        cleared = guarantee_sweep(db)
        overdue = dunning_sweep(db)
        print(f"guarantee_sweep: cleared={cleared}")
        print(f"dunning_sweep: overdue={len(overdue)} (delivery stubbed until B.10/SES)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
