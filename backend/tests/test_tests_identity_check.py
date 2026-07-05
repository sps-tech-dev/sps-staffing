"""A4-P1 class-guard: ck_tests_one_identity — the staffing.tests row must carry
EXACTLY ONE identity pairing (staffing application+candidate OR academy
enrollment+student). Manually verified at STOP-1; this makes it a permanent DB
guard (same discipline as the route-smoke matrix).

Note (A4-P2 carry-forward): this CHECK does NOT tie the pairing to
business_unit_id — BU↔pairing consistency is enforced at the ACADEMY issue path
(service layer), not here, so the constraint doesn't hardcode the BU axis value.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import get_sessionmaker


def _insert(db, tid, cols: dict):
    keys = ",".join(cols)
    vals = ",".join(f":{k}" for k in cols)
    db.execute(text(
        "INSERT INTO staffing.tests (tenant_id, business_unit_id, link_token_hash, "
        f"valid_until, {keys}) VALUES (:t, 'STAFFING', :h, now(), {vals})"),
        {"t": str(tid), "h": f"guard-{uuid.uuid4()}", **{k: str(v) for k, v in cols.items()}})


def test_ck_tests_one_identity_guard():
    db = get_sessionmaker()()
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    u = lambda: uuid.uuid4()  # noqa: E731
    try:
        # 1) academy pairing (enrollment+student, staffing side null) → SUCCEEDS.
        #    (enrollment_id/student_id are soft-refs — no FK — so random uuids insert.)
        _insert(db, tid, {"enrollment_id": u(), "student_id": u()})
        db.rollback()   # accepted; don't keep the probe row

        # 2) mixed row (application_id + student_id) → rejected by the CHECK
        with pytest.raises(IntegrityError):
            _insert(db, tid, {"application_id": u(), "student_id": u()})
        db.rollback()

        # 3) half row (application_id only, candidate_id null) → rejected
        with pytest.raises(IntegrityError):
            _insert(db, tid, {"application_id": u()})
        db.rollback()

        # 4) all four null → rejected (no pairing at all)
        with pytest.raises(IntegrityError):
            db.execute(text(
                "INSERT INTO staffing.tests (tenant_id, business_unit_id, link_token_hash, "
                "valid_until) VALUES (:t, 'STAFFING', :h, now())"),
                {"t": str(tid), "h": f"guard-{uuid.uuid4()}"})
        db.rollback()
    finally:
        db.rollback()
        db.close()
