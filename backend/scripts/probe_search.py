"""One-off B.4 real-op verification on dev RDS — runs on the BACKEND task def (sps_app).

Proves on REAL Postgres/RDS what local can't: the search_doc trigger fires under
the app role, the GIN index + websearch ranking behave, latency is sane, and the
erasure interplay holds (soft-delete/anonymize → search_doc NULL + absent).

Probe rows tagged '[B.4 probe]'; business rows cleaned here (sps_app has DML on
candidates); no timeline rows are created (direct ORM inserts, no API), so no
master cleanup is needed this time. Exits non-zero on any failure.
"""
from __future__ import annotations

import sys
import time

from sqlalchemy import delete, func, select, text

from app.db import get_sessionmaker
from app.models_staffing import Candidate

TAG = "[B.4 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ok = False
    try:
        a = Candidate(tenant_id=tid, full_name=f"Probe Fortran Name {TAG}")          # weight A
        b = Candidate(tenant_id=tid, full_name=f"Probe Skill Holder {TAG}",
                      skills=["fortran", "b4probe"], total_exp=6)                    # weight B
        c = Candidate(tenant_id=tid, full_name=f"Probe Resume Holder {TAG}",
                      resume_text="legacy fortran maintenance experience")           # weight C
        db.add_all([a, b, c]); db.commit()
        docs = db.execute(text(
            "SELECT count(*) FROM staffing.candidates WHERE full_name LIKE :t AND search_doc IS NOT NULL"),
            {"t": f"%{TAG}%"}).scalar_one()
        assert docs == 3, f"trigger did not populate search_doc ({docs}/3)"
        print("1. trigger populated search_doc on INSERT for 3 probe rows ✅")

        tsq = func.websearch_to_tsquery("simple", "fortran")
        t0 = time.perf_counter()
        rows = db.execute(
            select(Candidate.id, Candidate.full_name)
            .where(Candidate.tenant_id == tid, Candidate.deleted_at.is_(None),
                   Candidate.search_doc.op("@@")(tsq))
            .order_by(func.ts_rank(Candidate.search_doc, tsq).desc())).all()
        ms = (time.perf_counter() - t0) * 1000
        got = [r.id for r in rows]
        assert got == [a.id, b.id, c.id], f"ranking wrong: {[r.full_name for r in rows]}"
        print(f"2. websearch ranking A>B>C correct on real RDS in {ms:.1f}ms ✅ (<300ms target)")

        skl = db.execute(
            select(Candidate.id)
            .where(Candidate.tenant_id == tid, Candidate.deleted_at.is_(None),
                   Candidate.skills.contains(["fortran"]),
                   Candidate.total_exp >= 5)).scalars().all()
        assert skl == [b.id], "skill+exp filter wrong"
        print("3. skills @> + exp filter correct ✅")

        b.deleted_at = func.now()   # erasure-style soft delete → trigger must NULL the doc
        db.commit(); db.expire_all()
        doc = db.execute(text("SELECT search_doc FROM staffing.candidates WHERE id=:i"),
                         {"i": str(b.id)}).scalar_one()
        assert doc is None, "trigger did not NULL search_doc on soft-delete"
        left = db.execute(
            select(Candidate.id)
            .where(Candidate.tenant_id == tid, Candidate.deleted_at.is_(None),
                   Candidate.search_doc.op("@@")(tsq))).scalars().all()
        assert b.id not in left
        print("4. erasure interplay ✅ — soft-deleted row: search_doc NULL + absent from results")
        ok = True
    finally:
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("5. probe rows cleaned up")
    print("B.4 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
