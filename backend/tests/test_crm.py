"""B.12 CRM: lead CRUD, BU scoping (the anti-fork), the mini transition guard
(lost-requires-reason, terminals), activities stream, convert idempotency, gates."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import get_sessionmaker
from app.main import app
from app.models import Activity, BusinessUnit, ClientUser, Lead, Membership, Tenant, User
from app.models_staffing import Client, Job

HOST = {"host": "spstechnosoft.com"}
PW = "CrmLocal!123"
RECRUITER = "crm-rec@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Crm Tester", status="active")
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
    db.execute(delete(Activity).where(Activity.tenant_id == sps.id))
    db.execute(delete(Lead).where(Lead.tenant_id == sps.id))
    db.execute(delete(Job).where(Job.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _mk_lead(c, company="Acme BD Target"):
    r = c.post("/api/leads", json={"company": company, "contact_name": "Ravi BD",
                                   "contact_email": "ravi@acme.example",
                                   "source": "referral"}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()


def _t(c, lid, to_stage, reason=None):
    body = {"to_stage": to_stage}
    if reason:
        body["reason"] = reason
    return c.post(f"/api/leads/{lid}/transition", json=body, headers=HOST)


def _walk_to_won(c, lid):
    for st in ("qualified", "proposal", "negotiation", "won"):
        r = _t(c, lid, st)
        assert r.status_code == 200, (st, r.text)


def test_crud_and_bu_scoping(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = _mk_lead(c)
    assert lead["stage"] == "new" and lead["business_unit_id"] == "STAFFING"
    assert lead["owner_id"] is not None
    # a CONSULTING lead in the same tenant is INVISIBLE to the staffing context
    db.add(Lead(tenant_id=sps.id, business_unit_id="CONSULTING",
                company="Consulting Prospect"))
    db.commit()
    listed = c.get("/api/leads", headers=HOST).json()
    assert all(x["business_unit_id"] == "STAFFING" for x in listed)
    assert not any(x["company"] == "Consulting Prospect" for x in listed), \
        "BU scoping broken: staffing sees consulting leads"
    # patch non-stage fields
    r = c.patch(f"/api/leads/{lead['id']}", json={"contact_phone": "+91-9000000001"},
                headers=HOST)
    assert r.status_code == 200 and r.json()["contact_phone"] == "+91-9000000001"


def test_transition_guard(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = _mk_lead(c)
    # illegal jump
    r = _t(c, lead["id"], "won")
    assert r.status_code == 409 and r.json()["error"]["code"] == "ILLEGAL_TRANSITION"
    # legal walk
    _walk_to_won(c, lead["id"])
    # terminal
    assert _t(c, lead["id"], "qualified").status_code == 409
    # lost requires reason
    lead2 = _mk_lead(c, company="Lost Deal Co")
    r = _t(c, lead2["id"], "lost")
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    r = _t(c, lead2["id"], "lost", reason="chose a competitor")
    assert r.status_code == 200 and r.json()["lost_reason"] == "chose a competitor"
    assert _t(c, lead2["id"], "qualified").status_code == 409     # lost terminal


def test_activities_stream(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = _mk_lead(c)
    c.post(f"/api/leads/{lead['id']}/activities",
           json={"type": "call", "notes": "intro call, positive"}, headers=HOST)
    _t(c, lead["id"], "qualified")
    acts = c.get(f"/api/leads/{lead['id']}/activities", headers=HOST).json()
    types = [a["type"] for a in acts]
    assert types == ["created", "call", "stage_change"]           # chronological
    assert "new → qualified" in acts[-1]["notes"]


def test_convert_idempotent(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = _mk_lead(c, company="Winner Corp")
    # convert before won → 409
    assert c.patch(f"/api/leads/{lead['id']}/convert", json={},
                   headers=HOST).status_code == 409
    _walk_to_won(c, lead["id"])
    r = c.patch(f"/api/leads/{lead['id']}/convert",
                json={"job_title": "Platform Engineer"}, headers=HOST)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_converted"] is False and body["client_id"]
    assert body.get("job_id")
    client = db.get(Client, uuid.UUID(body["client_id"]))
    assert client.name == "Winner Corp"
    job = db.get(Job, uuid.UUID(body["job_id"]))
    assert job.title == "Platform Engineer" and str(job.client_id) == body["client_id"]
    # double convert → same client, NO duplicate
    r2 = c.patch(f"/api/leads/{lead['id']}/convert", json={}, headers=HOST)
    assert r2.status_code == 200 and r2.json()["already_converted"] is True
    assert r2.json()["client_id"] == body["client_id"]
    n = db.execute(select(func.count()).select_from(Client).where(
        Client.tenant_id == sps.id, Client.name == "Winner Corp")).scalar_one()
    assert n == 1, "double convert created a duplicate client!"


def test_convert_consulting_not_built(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = Lead(tenant_id=sps.id, business_unit_id="CONSULTING",
                company="Consult Convert Co", stage="won")
    db.add(lead); db.commit()
    # the staffing context can't even SEE it (404 via BU scoping) — prove the
    # consulting branch guard directly at the function level
    from app.context import RequestContext
    from app.routers.crm import convert_lead, ConvertIn
    from fastapi import HTTPException
    ctx = RequestContext(tenant_id=str(sps.id), business_unit_id="CONSULTING",
                         user_id=None, roles=("recruiter",))
    with pytest.raises(HTTPException) as e:
        convert_lead(lead_id=lead.id, body=ConvertIn(), ctx=ctx, db=db, idempotency_key=None)
    assert e.value.status_code == 400 and e.value.detail["code"] == "NOT_BUILT"


def test_gates_and_tenant_isolation(env):
    sps, db = env
    c = TestClient(app); _login(c, RECRUITER)
    lead = _mk_lead(c)
    assert TestClient(app).get("/api/leads", headers=HOST).status_code == 401
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB14")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB14", slug="testb14", name="Tenant B14"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
        db.commit()
    ub = _mk_user(db, tb, "crm-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb14.spstechnosoft.com"}
    try:
        cb = TestClient(app); _login(cb, "crm-b@local.test", B_HOST)
        assert cb.get("/api/leads", headers=B_HOST).json() == []
        assert cb.get(f"/api/leads/{lead['id']}", headers=B_HOST).status_code == 404
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()
