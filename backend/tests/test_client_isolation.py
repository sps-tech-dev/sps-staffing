"""Cross-CLIENT leakage test — the proof that nested client isolation holds.

Within ONE tenant (SPS001), client-user A (Acme) must read ONLY Acme's
jobs/applications/submissions/offers/interviews — never Globex's — and vice versa;
and no client can read across tenants. Isolation comes from TenantScopedRepo.base_query
nesting a client_id filter under the tenant_id filter (driven by the verified JWT's
client_id). This is the analog of test_tenant_isolation and MUST pass before any
client-portal UI is built.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import ClientUser, Tenant, User
from app.models_staffing import Application, Candidate, Client, Interview, Job, Offer, Submission
from app.repositories import TenantScopedRepo

BU = "STAFFING"


@pytest.fixture
def db():
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


def _client(db, tid, name):
    c = Client(tenant_id=tid, business_unit_id=BU, name=name); db.add(c); db.flush(); return c


def _pipeline(db, tid, client_id, cand_name):
    """A full pipeline owned by one client: job→candidate→application→submission→offer→interview."""
    job = Job(tenant_id=tid, business_unit_id=BU, title=f"{cand_name} Job", client_id=client_id); db.add(job); db.flush()
    cand = Candidate(tenant_id=tid, full_name=cand_name); db.add(cand); db.flush()
    appn = Application(tenant_id=tid, business_unit_id=BU, job_id=job.id, candidate_id=cand.id,
                       client_id=client_id, stage="submitted"); db.add(appn); db.flush()
    db.add(Submission(tenant_id=tid, business_unit_id=BU, application_id=appn.id, client_id=client_id))
    db.add(Offer(tenant_id=tid, business_unit_id=BU, application_id=appn.id, client_id=client_id))
    db.add(Interview(tenant_id=tid, business_unit_id=BU, application_id=appn.id, client_id=client_id, mode="video"))
    db.flush()
    return job, cand, appn


@pytest.fixture
def world(db):
    """Two clients (Acme, Globex) in SPS001, each with a full pipeline + a bound client user;
    plus a throwaway tenant B for the cross-tenant direction."""
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    acme = _client(db, sps.id, "ISO Acme"); globex = _client(db, sps.id, "ISO Globex")
    a_job, a_cand, _ = _pipeline(db, sps.id, acme.id, "Iso Acme Cand")
    g_job, g_cand, _ = _pipeline(db, sps.id, globex.id, "Iso Globex Cand")
    # bound client users (the binding that would give each a client-scoped session)
    uA = User(tenant_id=sps.id, email="iso-acme@local.test", password_hash="!", full_name="A", status="active")
    uB = User(tenant_id=sps.id, email="iso-globex@local.test", password_hash="!", full_name="B", status="active")
    db.add_all([uA, uB]); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=uA.id, client_id=acme.id, status="active"))
    db.add(ClientUser(tenant_id=sps.id, user_id=uB.id, client_id=globex.id, status="active"))
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB", slug="testb", name="Test Tenant B"); db.add(tb); db.flush()
    db.commit()
    yield dict(sps=sps, acme=acme, globex=globex, a_job=a_job, g_job=g_job,
               a_cand=a_cand, g_cand=g_cand, uA=uA, uB=uB, tb=tb)
    # teardown
    for M in (Interview, Offer, Submission, Application, Job, Candidate):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(ClientUser).where(ClientUser.tenant_id == sps.id))
    db.execute(delete(User).where(User.id.in_([uA.id, uB.id])))
    db.execute(delete(Client).where(Client.tenant_id == sps.id, Client.name.in_(["ISO Acme", "ISO Globex"])))
    db.execute(delete(Tenant).where(Tenant.code == "TESTB"))
    db.commit()


def _ctx(tid, client_id):
    return RequestContext(tenant_id=str(tid), business_unit_id=BU, client_id=str(client_id) if client_id else None,
                          roles=("client",))


def test_cross_client_pipeline_isolation(db, world):
    acme, globex = world["acme"], world["globex"]
    repo_a = TenantScopedRepo(db, _ctx(world["sps"].id, acme.id))
    repo_b = TenantScopedRepo(db, _ctx(world["sps"].id, globex.id))

    # every client-owned model is isolated, BOTH directions
    for M in (Job, Application, Submission, Offer, Interview):
        a_ids = {r.client_id for r in repo_a.scoped_all(M)}
        b_ids = {r.client_id for r in repo_b.scoped_all(M)}
        assert a_ids in ({acme.id}, set()), f"LEAK: Acme sees other clients' {M.__name__}: {a_ids}"
        assert globex.id not in a_ids, f"LEAK: Acme can read Globex {M.__name__}"
        assert acme.id not in b_ids, f"LEAK: Globex can read Acme {M.__name__}"
        # each side actually sees its own
        assert acme.id in a_ids and globex.id in b_ids, f"{M.__name__} should be visible to its owner"

    # candidates are reached ONLY via the client-scoped pipeline (pool is not client-owned):
    a_app_cands = {a.candidate_id for a in repo_a.scoped_all(Application)}
    assert world["a_cand"].id in a_app_cands and world["g_cand"].id not in a_app_cands, \
        "LEAK: Acme can reach Globex's submitted candidate via the pipeline"


def test_client_cannot_read_across_tenants(db, world):
    # a client context in tenant B can read NONE of SPS001's client-owned rows
    repo_tb = TenantScopedRepo(db, _ctx(world["tb"].id, world["acme"].id))  # even with Acme's client_id
    for M in (Job, Application, Submission, Offer, Interview):
        assert repo_tb.scoped_all(M) == [], f"LEAK: tenant B context read SPS {M.__name__}"


def test_staff_session_is_not_client_restricted(db, world):
    # a staff session (no client_id) sees BOTH clients' jobs — nesting restricts only client sessions
    staff = TenantScopedRepo(db, _ctx(world["sps"].id, None))
    job_clients = {j.client_id for j in staff.scoped_all(Job)}
    assert world["acme"].id in job_clients and world["globex"].id in job_clients, \
        "staff (no client_id) must see all clients' jobs"
