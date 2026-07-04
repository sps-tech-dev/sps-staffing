"""B.8 interview scheduling depth: slot propose/choose, .ics validity + SEQUENCE,
no-show reason, reschedule re-opens, timeline events, scoping."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app import ics as ics_mod
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateTimeline, Client, Interview, InterviewSlot, Job,
)

HOST = {"host": "spstechnosoft.com"}
PW = "SlotLocal!123"
RECRUITER = "slot-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Slot Tester", status="active")
    db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == tenant.id,
                                               BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=roles))
    db.commit()
    return u


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    rec = _mk_user(db, sps, RECRUITER, ["recruiter"])
    yield sps, db
    db.execute(delete(InterviewSlot).where(InterviewSlot.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Interview, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _mk_interview(c, phone="9821200001"):
    job = c.post("/api/jobs", json={"title": "Slot Job"}, headers=HOST).json()
    cand = c.post("/api/candidates", json={"full_name": "Slot Cand", "phone": phone,
                                           "email": "slot-cand@local.test"}, headers=HOST).json()
    aid = c.post("/api/applications", json={"job_id": job["id"], "candidate_id": cand["id"]},
                 headers=HOST).json()["id"]
    iv = c.post(f"/api/applications/{aid}/interviews", json={"mode": "video",
                "interviewer_name": "Priya"}, headers=HOST).json()
    return cand["id"], aid, iv["id"]


def _slots(n=3, base_hour=10):
    base = dt.datetime(2026, 8, 3, base_hour, 0, tzinfo=dt.timezone.utc)
    return [{"start": (base + dt.timedelta(days=k)).isoformat(),
             "end": (base + dt.timedelta(days=k, hours=1)).isoformat()} for k in range(n)]


def test_propose_requires_three_and_choose_schedules(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, _aid, ivid = _mk_interview(c)
    r = c.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(2)}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "TOO_FEW_SLOTS"
    bad = _slots(3); bad[0]["end"] = bad[0]["start"]                 # end == start
    assert c.post(f"/api/interviews/{ivid}/slots", json={"slots": bad},
                  headers=HOST).status_code == 422
    r = c.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3)}, headers=HOST)
    assert r.status_code == 200 and len(r.json()["slots"]) == 3

    slot = r.json()["slots"][1]
    ch = c.post(f"/api/interviews/{ivid}/slots/{slot['id']}/choose", headers=HOST)
    assert ch.status_code == 200
    body = ch.json()
    assert body["status"] == "scheduled" and body["scheduled_at"] == slot["start"]
    assert body["ics_path"].endswith("/ics") and body["ics_sequence"] == 0
    listed = c.get(f"/api/interviews/{ivid}/slots", headers=HOST).json()
    assert [s["chosen"] for s in listed].count(True) == 1
    # timeline Interview event with action=scheduled (plus the create-time one)
    tl = c.get(f"/api/candidates/{cid}/timeline", headers=HOST,
               params={"event_type": "Interview"}).json()
    assert any(e["payload"].get("action") == "scheduled" for e in tl)


def test_ics_valid_and_sequence_bumps_on_reschedule(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, _aid, ivid = _mk_interview(c)
    r = c.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3)}, headers=HOST).json()
    c.post(f"/api/interviews/{ivid}/slots/{r['slots'][0]['id']}/choose", headers=HOST)
    ics1 = c.get(f"/api/interviews/{ivid}/ics", headers=HOST)
    assert ics1.status_code == 200 and ics1.headers["content-type"].startswith("text/calendar")
    t = ics1.text
    for token in ("BEGIN:VCALENDAR", "BEGIN:VEVENT", f"UID:interview-{ivid}@",
                  "SEQUENCE:0", "DTSTART:20260803T100000Z", "DTEND:20260803T110000Z",
                  "SUMMARY:", "ORGANIZER;", "END:VEVENT", "END:VCALENDAR"):
        assert token in t, f"missing {token}"
    assert "\r\n" in t                                              # RFC 5545 CRLF

    # reschedule: SEQUENCE bumps, slots wiped, fresh .ics after the next choose
    rs = c.patch(f"/api/interviews/{ivid}", json={"status": "rescheduled",
                 "reason": "panelist unavailable"}, headers=HOST)
    assert rs.status_code == 200 and rs.json()["status"] == "rescheduled"
    assert c.get(f"/api/interviews/{ivid}/slots", headers=HOST).json() == []   # re-opened
    assert c.get(f"/api/interviews/{ivid}/ics", headers=HOST).status_code == 404
    r2 = c.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3, base_hour=15)},
                headers=HOST).json()
    c.post(f"/api/interviews/{ivid}/slots/{r2['slots'][2]['id']}/choose", headers=HOST)
    ics2 = c.get(f"/api/interviews/{ivid}/ics", headers=HOST).text
    assert "SEQUENCE:1" in ics2 and f"UID:interview-{ivid}@" in ics2   # same UID, bumped SEQ
    assert "DTSTART:20260805T150000Z" in ics2


def test_no_show_requires_reason(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, _aid, ivid = _mk_interview(c)
    r = c.patch(f"/api/interviews/{ivid}", json={"status": "no_show"}, headers=HOST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    ok = c.patch(f"/api/interviews/{ivid}", json={"status": "no_show",
                 "reason": "candidate unreachable"}, headers=HOST)
    assert ok.status_code == 200 and ok.json()["status"] == "no_show"
    row = db.execute(select(Interview).where(Interview.id == uuid.UUID(ivid))).scalar_one()
    db.refresh(row)
    assert row.status_reason == "candidate unreachable"


def test_idempotent_replays_no_dup(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    cid, _aid, ivid = _mk_interview(c)
    r = c.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3)}, headers=HOST).json()
    key = f"slot-idem-{uuid.uuid4()}"
    h = {**HOST, "Idempotency-Key": key}
    c1 = c.post(f"/api/interviews/{ivid}/slots/{r['slots'][0]['id']}/choose", headers=h)
    c2 = c.post(f"/api/interviews/{ivid}/slots/{r['slots'][0]['id']}/choose", headers=h)
    assert c1.json() == c2.json()
    n = db.execute(select(func.count()).select_from(CandidateTimeline).where(
        CandidateTimeline.candidate_id == uuid.UUID(cid),
        CandidateTimeline.event_type == "Interview")).scalar_one()
    assert n == 2, f"expected create+scheduled events only, got {n}"   # no replay dup


def test_scoping_and_client_readonly_view(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    _cid, _aid, ivid = _mk_interview(c)
    # unauth → 401
    assert TestClient(app).post(f"/api/interviews/{ivid}/slots",
                                json={"slots": _slots(3)}, headers=HOST).status_code == 401
    # tenant B → 404
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB10")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB10", slug="testb10", name="Tenant B10"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "slot-b@local.test", ["recruiter"])
    try:
        cb = TestClient(app); _login(cb, "slot-b@local.test", {"host": "testb10.spstechnosoft.com"})
        assert cb.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3)},
                       headers={"host": "testb10.spstechnosoft.com"}).status_code == 404
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
    # client portal surfaces the new status read-only (status passed through verbatim)
    c.patch(f"/api/interviews/{ivid}", json={"status": "rescheduled"}, headers=HOST)
    iv = db.execute(select(Interview).where(Interview.id == uuid.UUID(ivid))).scalar_one()
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Slot ClientCo")
    db.add(client); db.flush()
    iv.client_id = client.id                                   # bind for the portal view
    u = User(tenant_id=sps.id, email="slot-client@local.test",
             password_hash=PasswordHasher().hash(PW), full_name="SC", status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id, status="active"))
    db.commit()
    try:
        cc = TestClient(app); _login(cc, "slot-client@local.test")
        rows = cc.get("/api/client/interviews", headers=HOST).json()
        assert rows and rows[0]["status"] == "rescheduled"     # visible, read-only
        # and the client cannot touch the scheduling endpoints
        assert cc.post(f"/api/interviews/{ivid}/slots", json={"slots": _slots(3)},
                       headers=HOST).status_code == 403
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        iv2 = db.execute(select(Interview).where(Interview.id == uuid.UUID(ivid))).scalar_one()
        iv2.client_id = None
        db.execute(delete(Client).where(Client.id == client.id)); db.commit()
