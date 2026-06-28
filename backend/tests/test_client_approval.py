"""Admin approval gate: pending request → approve LINKS+activates → client can log in
with a client-scoped session; reject path; only approval grants access."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientRegistrationRequest, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import Client
from app.security import decode_access_token

HOST = {"host": "spstechnosoft.com"}
ADMIN_PW = "AdminLocal!123"
ADMIN = "client-approver@local.test"
CLIENT_PW = "ClientInit!123"
CLIENT_EMAIL = "ceo@newco.test"


def _mk_admin(db, sps):
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == ADMIN))
    u = User(tenant_id=sps.id, email=ADMIN, password_hash=PasswordHasher().hash(ADMIN_PW),
             full_name="Approver", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["admin"])); db.commit()
    return u


@pytest.fixture
def env():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    admin = _mk_admin(db, sps)
    yield sps, admin
    # teardown: users created for the client + their bindings/consents/client
    cu = db.execute(select(ClientUser).where(ClientUser.tenant_id == sps.id)).scalars().all()
    uids = [x.user_id for x in cu]
    db.execute(delete(ClientUser).where(ClientUser.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    db.execute(delete(ClientRegistrationRequest).where(ClientRegistrationRequest.tenant_id == sps.id))
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == CLIENT_EMAIL))
    if uids:
        db.execute(delete(User).where(User.id.in_(uids)))
    db.execute(delete(Client).where(Client.tenant_id == sps.id, Client.name == "NewCo Pvt Ltd"))
    db.execute(delete(Membership).where(Membership.user_id == admin.id))
    db.execute(delete(User).where(User.id == admin.id)); db.commit(); db.close()


def _admin_client():
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": ADMIN, "password": ADMIN_PW}, headers=HOST).status_code == 200
    return c


def _register():
    pub = TestClient(app)
    r = pub.post("/api/register/client", json={
        "company_name": "NewCo Pvt Ltd", "industry": "IT", "contact_person": "Sana Khan",
        "email": CLIENT_EMAIL, "phone": "9812355566", "captcha_token": "t", "consent_data_processing": True},
        headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_approve_links_activates_and_enables_client_login(env):
    sps, _ = env
    req_id = _register()
    c = _admin_client()

    # admin sees the pending request
    items = c.get("/api/admin/client-registrations?status=pending", headers=HOST).json()["items"]
    assert any(i["id"] == req_id and i["company_name"] == "NewCo Pvt Ltd" for i in items)

    # before approval: no client login exists (grants nothing)
    pre = TestClient(app).post("/api/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, headers=HOST)
    assert pre.status_code == 401

    # approve → create a new client + activate the binding
    appr = c.post(f"/api/admin/client-registrations/{req_id}/approve",
                  json={"create_new_client": True, "initial_password": CLIENT_PW}, headers=HOST)
    assert appr.status_code == 200, appr.text
    assert appr.json()["status"] == "approved"
    client_id = appr.json()["client_id"]

    # the active binding now exists
    db = get_sessionmaker()()
    cu = db.execute(select(ClientUser).where(ClientUser.tenant_id == sps.id)).scalars().all()
    assert len(cu) == 1 and cu[0].status == "active" and str(cu[0].client_id) == client_id
    db.close()

    # the client can now log in → role 'client', routed to the client portal, with client scope
    login = TestClient(app).post("/api/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, headers=HOST)
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "client" and login.json()["home"] == "/client"
    token = login.cookies.get("access_token")
    claims = decode_access_token(token)
    assert claims.get("client_id") == client_id, "JWT must carry the bound client_id"


def test_client_session_rejected_by_staff_and_admin_endpoints(env):
    """A bound client session must NOT reach staff/admin endpoints (which are NOT
    client-scoped) — else /employer/* etc. would leak tenant-wide data."""
    sps, _ = env
    req_id = _register()
    a = _admin_client()
    a.post(f"/api/admin/client-registrations/{req_id}/approve",
           json={"create_new_client": True, "initial_password": CLIENT_PW}, headers=HOST)
    cli = TestClient(app)  # persistent session → keeps the client cookie
    assert cli.post("/api/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, headers=HOST).status_code == 200
    # staff endpoints (raw tenant-scoped, not client-scoped) → 403 for a client session
    for path in ("/api/submissions", "/api/offers", "/api/interviews", "/api/invoices", "/api/vendors"):
        assert cli.get(path, headers=HOST).status_code == 403, f"LEAK risk: client reached {path}"
    assert cli.post("/api/jobs", json={"title": "x"}, headers=HOST).status_code == 403
    assert cli.get("/api/admin/clients", headers=HOST).status_code == 403


def test_reject_keeps_no_access(env):
    sps, _ = env
    req_id = _register()
    c = _admin_client()
    rej = c.post(f"/api/admin/client-registrations/{req_id}/reject", headers=HOST)
    assert rej.status_code == 200 and rej.json()["status"] == "rejected"
    # re-approving a non-pending request is refused
    assert c.post(f"/api/admin/client-registrations/{req_id}/approve",
                  json={"create_new_client": True, "initial_password": CLIENT_PW}, headers=HOST).status_code == 409


def test_approval_requires_admin(env):
    sps, _ = env
    req_id = _register()
    # a non-admin (candidate) cannot approve
    db = get_sessionmaker()()
    db.execute(delete(User).where(User.email == "notadmin@local.test"))
    u = User(tenant_id=sps.id, email="notadmin@local.test", password_hash=PasswordHasher().hash(ADMIN_PW),
             full_name="X", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["candidate"])); db.commit()
    try:
        nc = TestClient(app)
        nc.post("/api/auth/login", json={"email": "notadmin@local.test", "password": ADMIN_PW}, headers=HOST)
        assert nc.post(f"/api/admin/client-registrations/{req_id}/approve",
                       json={"create_new_client": True, "initial_password": CLIENT_PW}, headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
