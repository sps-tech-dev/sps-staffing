"""THE GATE for client-internal roles (Task 7) — owner-scoping + offer-write permission.

Within ONE client (already isolated by tenant_id + client_id), two client-user roles:
  • client_admin (HR)      → sees ALL the client's jobs + full pipelines; ONLY role that
                             can write offers (release + joining date); can reassign jobs
                             and manage teammates.
  • client_manager (mgr)   → sees the FULL pipeline of ONLY their OWN posted jobs
                             (owner_user_id = self); offer card is READ-ONLY (403 on write).

Two independent axes, both proven here:
  (a) ROW SCOPE  — base_query nests owner_user_id=self for a client_manager (no cross-
                   manager visibility), no owner filter for a client_admin.
  (b) OFFER-WRITE PERMISSION — release / joining-date gated to client_admin; manager 403
                   write / 200 read; HR writes; released offer surfaces read-only on the
                   manager's own job.

This MUST pass before any UI is built on top (and again in the final E2E).
"""
from __future__ import annotations

import datetime

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.context import RequestContext
from app.db import get_sessionmaker
from app.main import app
from app.models import ClientUser, Tenant, User
from app.models_staffing import Application, Candidate, Client, Interview, Job, Offer, Submission
from app.repositories import TenantScopedRepo

BU = "STAFFING"
HOST = {"host": "spstechnosoft.com"}
PW = "OwnerScope!1"


def _user(db, sps, email, role, client_id):
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == email))
    u = User(tenant_id=sps.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name=email.split("@")[0], status="active"); db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client_id, status="active", role=role))
    return u


def _pipeline(db, sps, client_id, owner_user_id, cand_name):
    """A full owner-stamped pipeline: job→cand→application→submission→offer(draft)→interview."""
    job = Job(tenant_id=sps.id, business_unit_id=BU, title=f"{cand_name} Role", client_id=client_id,
              owner_user_id=owner_user_id, status="open"); db.add(job); db.flush()
    cand = Candidate(tenant_id=sps.id, full_name=cand_name); db.add(cand); db.flush()
    appn = Application(tenant_id=sps.id, business_unit_id=BU, job_id=job.id, candidate_id=cand.id,
                       client_id=client_id, owner_user_id=owner_user_id, stage="offer"); db.add(appn); db.flush()
    sub = Submission(tenant_id=sps.id, business_unit_id=BU, application_id=appn.id,
                     client_id=client_id, owner_user_id=owner_user_id); db.add(sub)
    offer = Offer(tenant_id=sps.id, business_unit_id=BU, application_id=appn.id, client_id=client_id,
                  owner_user_id=owner_user_id, ctc=1200000, status="draft"); db.add(offer)
    db.add(Interview(tenant_id=sps.id, business_unit_id=BU, application_id=appn.id, client_id=client_id,
                     owner_user_id=owner_user_id, mode="video"))
    db.flush()
    return job, appn, offer


@pytest.fixture
def world():
    """One client (OS Acme) with HR + manager A + manager B; A owns one pipeline, B another."""
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    acme = Client(tenant_id=sps.id, business_unit_id=BU, name="OS Acme"); db.add(acme); db.flush()
    hr = _user(db, sps, "os-hr@local.test", "client_admin", acme.id)
    mA = _user(db, sps, "os-mgrA@local.test", "client_manager", acme.id)
    mB = _user(db, sps, "os-mgrB@local.test", "client_manager", acme.id)
    db.flush()
    a_job, a_app, a_offer = _pipeline(db, sps, acme.id, mA.id, "OS Acme A Cand")
    b_job, b_app, b_offer = _pipeline(db, sps, acme.id, mB.id, "OS Acme B Cand")
    db.commit()
    ids = dict(sps_id=sps.id, acme_id=acme.id,
               hr=hr.id, mA=mA.id, mB=mB.id,
               a_job=str(a_job.id), b_job=str(b_job.id),
               a_offer=str(a_offer.id), b_offer=str(b_offer.id))
    yield ids
    for M in (Interview, Offer, Submission, Application, Job, Candidate):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(ClientUser).where(ClientUser.tenant_id == sps.id, ClientUser.client_id == acme.id))
    db.execute(delete(User).where(User.id.in_([hr.id, mA.id, mB.id])))
    db.execute(delete(Client).where(Client.id == acme.id))
    db.commit(); db.close()


# ── (a) ROW SCOPE at the base layer ──────────────────────────────────
def _ctx(tid, client_id, role, user_id):
    return RequestContext(tenant_id=str(tid), business_unit_id=BU, client_id=str(client_id),
                          client_role=role, user_id=str(user_id), roles=("client",))


def test_manager_sees_only_own_pipeline_both_directions(world):
    db = get_sessionmaker()()
    try:
        repo_a = TenantScopedRepo(db, _ctx(world["sps_id"], world["acme_id"], "client_manager", world["mA"]))
        repo_b = TenantScopedRepo(db, _ctx(world["sps_id"], world["acme_id"], "client_manager", world["mB"]))
        for M in (Job, Application, Submission, Offer, Interview):
            a_owners = {str(r.owner_user_id) for r in repo_a.scoped_all(M)}
            b_owners = {str(r.owner_user_id) for r in repo_b.scoped_all(M)}
            # A sees only A's rows; B is invisible to A (and vice versa)
            assert a_owners in ({str(world["mA"])}, set()), f"LEAK: mgr A sees other owners' {M.__name__}: {a_owners}"
            assert str(world["mB"]) not in a_owners, f"LEAK: mgr A reads mgr B's {M.__name__}"
            assert str(world["mA"]) not in b_owners, f"LEAK: mgr B reads mgr A's {M.__name__}"
            assert str(world["mA"]) in a_owners and str(world["mB"]) in b_owners, \
                f"{M.__name__} should be visible to its owner"
    finally:
        db.close()


def test_hr_sees_all_client_jobs(world):
    db = get_sessionmaker()()
    try:
        repo_hr = TenantScopedRepo(db, _ctx(world["sps_id"], world["acme_id"], "client_admin", world["hr"]))
        job_ids = {str(j.id) for j in repo_hr.scoped_all(Job)}
        assert world["a_job"] in job_ids and world["b_job"] in job_ids, \
            "HR (client_admin) must see ALL the client's jobs (no owner filter)"
        # HR sees both managers' pipelines
        owners = {str(a.owner_user_id) for a in repo_hr.scoped_all(Application)}
        assert {str(world["mA"]), str(world["mB"])} <= owners
    finally:
        db.close()


# ── (b) OFFER-WRITE PERMISSION at the HTTP layer ─────────────────────
def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST)
    assert r.status_code == 200, r.text
    return c


def test_manager_jobs_scoped_over_http(world):
    c = _login("os-mgrA@local.test")
    job_ids = {j["id"] for j in c.get("/api/client/jobs", headers=HOST).json()}
    assert world["a_job"] in job_ids and world["b_job"] not in job_ids, \
        "LEAK: mgr A sees mgr B's job over HTTP"


def test_manager_can_read_offer_but_not_write(world):
    c = _login("os-mgrA@local.test")
    # READ own offer → 200, visible
    offers = c.get("/api/client/offers", headers=HOST).json()
    assert any(o["id"] == world["a_offer"] for o in offers), "mgr A should READ own offer"
    assert all(o["id"] != world["b_offer"] for o in offers), "LEAK: mgr A reads mgr B's offer"
    # WRITE own offer → 403 (HR-only gate)
    jd = {"joining_date": str(datetime.date(2026, 9, 1))}
    assert c.post(f"/api/client/offers/{world['a_offer']}/release", json=jd, headers=HOST).status_code == 403
    assert c.patch(f"/api/client/offers/{world['a_offer']}/joining-date", json=jd, headers=HOST).status_code == 403
    # WRITE another manager's offer → also 403 (gate fires before scope)
    assert c.post(f"/api/client/offers/{world['b_offer']}/release", json=jd, headers=HOST).status_code == 403


def test_hr_releases_offer_then_manager_sees_it_readonly(world):
    hr = _login("os-hr@local.test")
    jd = str(datetime.date(2026, 9, 15))
    r = hr.post(f"/api/client/offers/{world['a_offer']}/release",
                json={"joining_date": jd, "ctc": 1500000}, headers=HOST)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "released" and r.json()["joining_date"] == jd
    # the owning manager now sees the released offer — READ-ONLY (still 403 on write)
    mgr = _login("os-mgrA@local.test")
    seen = next(o for o in mgr.get("/api/client/offers", headers=HOST).json() if o["id"] == world["a_offer"])
    assert seen["status"] == "released" and seen["joining_date"] == jd
    assert mgr.patch(f"/api/client/offers/{world['a_offer']}/joining-date",
                     json={"joining_date": str(datetime.date(2026, 10, 1))}, headers=HOST).status_code == 403


def test_hr_reassign_works_manager_cannot(world):
    # manager cannot reassign → 403
    mgr = _login("os-mgrA@local.test")
    assert mgr.post(f"/api/client/jobs/{world['a_job']}/reassign",
                    json={"owner_user_id": str(world["mB"])}, headers=HOST).status_code == 403
    # HR reassigns A's job to manager B → 200, pipeline cascades
    hr = _login("os-hr@local.test")
    r = hr.post(f"/api/client/jobs/{world['a_job']}/reassign",
                json={"owner_user_id": str(world["mB"])}, headers=HOST)
    assert r.status_code == 200, r.text
    assert r.json()["pipeline_reassigned"] >= 1
    # now A no longer sees the job; B does
    a_jobs = {j["id"] for j in _login("os-mgrA@local.test").get("/api/client/jobs", headers=HOST).json()}
    b_jobs = {j["id"] for j in _login("os-mgrB@local.test").get("/api/client/jobs", headers=HOST).json()}
    assert world["a_job"] not in a_jobs, "after reassign, old owner must NOT see the job"
    assert world["a_job"] in b_jobs and world["b_job"] in b_jobs, "new owner sees the reassigned job + own"


def test_reassign_rejects_non_client_user(world):
    hr = _login("os-hr@local.test")
    import uuid as _uuid
    r = hr.post(f"/api/client/jobs/{world['a_job']}/reassign",
                json={"owner_user_id": str(_uuid.uuid4())}, headers=HOST)
    assert r.status_code == 422, "reassign to a non-member of this client must be rejected"


def test_team_management_hr_only(world):
    # manager cannot list or add teammates
    mgr = _login("os-mgrA@local.test")
    assert mgr.get("/api/client/team", headers=HOST).status_code == 403
    assert mgr.post("/api/client/team", json={"email": "x@local.test", "full_name": "X",
                    "initial_password": PW, "role": "client_manager"}, headers=HOST).status_code == 403
    # HR lists (HR + A + B) and can add a teammate
    hr = _login("os-hr@local.test")
    roster = hr.get("/api/client/team", headers=HOST).json()
    assert {m["role"] for m in roster} == {"client_admin", "client_manager"} and len(roster) == 3
    add = hr.post("/api/client/team", json={"email": "os-mgrC@local.test", "full_name": "Mgr C",
                  "initial_password": PW, "role": "client_manager"}, headers=HOST)
    assert add.status_code == 200, add.text
    # the new teammate can log in and gets a scoped, owner-empty (sees nothing yet) session
    cNew = _login("os-mgrC@local.test")
    assert cNew.get("/api/client/jobs", headers=HOST).json() == []
    # cleanup the extra user created by this test
    db = get_sessionmaker()()
    try:
        u = db.execute(select(User).where(User.email == "os-mgrC@local.test")).scalar_one()
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit()
    finally:
        db.close()
