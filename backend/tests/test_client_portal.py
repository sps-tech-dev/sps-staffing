"""Client portal endpoints: strictly client-scoped reads, scoped writes (feedback,
post job), and 403 for non-client sessions — HTTP-level proof on top of the repo gate."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import ClientUser, Tenant, User
from app.models_staffing import Application, Candidate, Client, Job, Submission

HOST = {"host": "spstechnosoft.com"}
PW = "ClientPortal!1"


def _client_user(db, sps, email, client_id):
    db.execute(delete(User).where(User.tenant_id == sps.id, User.email == email))
    u = User(tenant_id=sps.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Client", status="active"); db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client_id, status="active"))
    return u


def _pipeline(db, sps, client_id, cand_name):
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title=f"{cand_name} Role", client_id=client_id, status="open")
    db.add(job); db.flush()
    cand = Candidate(tenant_id=sps.id, full_name=cand_name); db.add(cand); db.flush()
    appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id, candidate_id=cand.id,
                       client_id=client_id, stage="submitted_to_client"); db.add(appn); db.flush()
    sub = Submission(tenant_id=sps.id, business_unit_id="STAFFING", application_id=appn.id, client_id=client_id)
    db.add(sub); db.flush()
    return job, sub


@pytest.fixture
def world():
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    acme = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="CP Acme")
    globex = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="CP Globex")
    db.add_all([acme, globex]); db.flush()
    a_job, a_sub = _pipeline(db, sps, acme.id, "CP Acme Cand")
    g_job, g_sub = _pipeline(db, sps, globex.id, "CP Globex Cand")
    uA = _client_user(db, sps, "cp-acme@local.test", acme.id)
    uB = _client_user(db, sps, "cp-globex@local.test", globex.id)
    db.commit()
    ids = dict(acme=str(acme.id), a_job=str(a_job.id), a_sub=str(a_sub.id),
               g_job=str(g_job.id), g_sub=str(g_sub.id), uA=uA.id, uB=uB.id)
    yield ids
    cu = db.execute(select(ClientUser).where(ClientUser.tenant_id == sps.id)).scalars().all()
    db.execute(delete(ClientUser).where(ClientUser.tenant_id == sps.id))
    for M in (Submission, Application, Job, Candidate):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Client).where(Client.tenant_id == sps.id, Client.name.in_(["CP Acme", "CP Globex"])))
    db.execute(delete(User).where(User.id.in_([x.user_id for x in cu])))
    db.commit(); db.close()


def _login(email):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": PW}, headers=HOST).status_code == 200
    return c


def test_client_sees_only_own_data(world):
    c = _login("cp-acme@local.test")
    job_ids = {j["id"] for j in c.get("/api/client/jobs", headers=HOST).json()}
    assert world["a_job"] in job_ids and world["g_job"] not in job_ids, "LEAK: Acme sees Globex jobs"
    subs = c.get("/api/client/submissions", headers=HOST).json()
    cands = {s["candidate"] for s in subs}
    assert "CP Acme Cand" in cands and "CP Globex Cand" not in cands, "LEAK: Acme sees Globex candidate"
    # overview + pipeline are scoped too
    ov = c.get("/api/client/overview", headers=HOST).json()
    assert ov["open_jobs"] == 1 and ov["in_pipeline"] == 1
    pipe = c.get("/api/client/pipeline", headers=HOST).json()["stages"]
    assert all(row["job"] == "CP Acme Cand Role" for rows in pipe.values() for row in rows)


def test_feedback_only_on_own_submission(world):
    c = _login("cp-acme@local.test")
    ok = c.post(f"/api/client/submissions/{world['a_sub']}/feedback", json={"decision": "approve", "note": "Great"}, headers=HOST)
    assert ok.status_code == 200 and ok.json()["status"] == "shortlisted"
    # Globex's submission is invisible to Acme → 404 (not 403 — it just doesn't exist for them)
    assert c.post(f"/api/client/submissions/{world['g_sub']}/feedback", json={"decision": "reject"}, headers=HOST).status_code == 404


def test_post_job_is_owned_by_the_client(world):
    c = _login("cp-acme@local.test")
    r = c.post("/api/client/jobs", json={"title": "New Client Job"}, headers=HOST)
    assert r.status_code == 200 and r.json()["status"] == "open"
    # the new job appears in the client's own list
    assert any(j["title"] == "New Client Job" for j in c.get("/api/client/jobs", headers=HOST).json())


def test_non_client_session_forbidden(world):
    # a staff/admin or candidate session (no client_id) cannot use the client portal
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    db.execute(delete(User).where(User.email == "cp-staff@local.test"))
    from app.models import BusinessUnit, Membership
    u = User(tenant_id=sps.id, email="cp-staff@local.test", password_hash=PasswordHasher().hash(PW),
             full_name="S", status="active"); db.add(u); db.flush()
    bu = db.execute(select(BusinessUnit).where(BusinessUnit.tenant_id == sps.id, BusinessUnit.code == "STAFFING")).scalar_one()
    db.add(Membership(user_id=u.id, business_unit_id=bu.id, roles=["recruiter"])); db.commit()
    try:
        c = _login("cp-staff@local.test")
        assert c.get("/api/client/overview", headers=HOST).status_code == 403
    finally:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id)); db.commit(); db.close()
