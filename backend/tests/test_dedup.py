"""B.3 duplicate detection: exact 409 unchanged, fuzzy create-then-flag (second-signal
guard), review queue, transactional merge (collision-aware), dismiss, isolation, gates."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateDupReview, CandidateTimeline, Client, Job,
    Vendor, VendorSubmission,
)

HOST = {"host": "spstechnosoft.com"}
PW = "DedupLocal!123"
RECRUITER = "dedup-rec@local.test"


def _mk_user(db, tenant, email, roles):
    # leftover-robust: delete a prior user's memberships/client bindings first
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Dedup Tester", status="active")
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
    yield sps
    db.execute(delete(CandidateDupReview).where(CandidateDupReview.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (VendorSubmission, Vendor, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _mk_cand(c, name, phone, skills=None):
    r = c.post("/api/candidates", json={"full_name": name, "phone": phone,
                                        "skills": skills or []}, headers=HOST)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _reviews(c, **params):
    r = c.get("/api/candidates/dup-reviews", headers=HOST, params=params or None)
    assert r.status_code == 200, r.text
    return r.json()


def test_similarity_resolves_via_app_engine(env):
    """search_path proof: public.similarity() resolves on the app's own connection."""
    db = get_sessionmaker()()
    assert db.execute(text("SELECT public.similarity('abc','abc')")).scalar_one() == 1.0
    db.close()


def test_exact_dup_still_409(env):
    c = TestClient(app); _login(c, RECRUITER)
    _mk_cand(c, "Exact Dup Person", "9866600001", ["python"])
    r = c.post("/api/candidates", json={"full_name": "Different Name Entirely",
                                        "phone": "9866600001"}, headers=HOST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_CANDIDATE"
    assert _reviews(c) == []                       # exact path never queues a review


def test_fuzzy_with_skill_overlap_creates_and_flags(env):
    c = TestClient(app); _login(c, RECRUITER)
    first = _mk_cand(c, "Deepak Kumar", "9866600011", ["Python", "AWS"])
    second = _mk_cand(c, "Deepak Kumarr", "9866600012", ["python"])   # created anyway
    revs = _reviews(c, status="pending")
    assert len(revs) == 1
    rv = revs[0]
    assert rv["candidate_id"] == second and rv["matched_candidate_id"] == first
    assert rv["match_type"] == "fuzzy" and rv["score"] >= 0.4 and rv["signal"] == "skills"


def test_name_alone_never_flags(env):
    c = TestClient(app); _login(c, RECRUITER)
    _mk_cand(c, "Deepak Kumar", "9866600021", ["python"])
    _mk_cand(c, "Deepak Kumarr", "9866600022", ["golang"])   # no skill overlap, no resume
    assert _reviews(c) == [], "fuzzy flagged on name alone — second-signal guard failed"


def test_register_path_flags_fuzzy(env):
    c = TestClient(app); _login(c, RECRUITER)
    first = _mk_cand(c, "Sunita Verma", "9866600031", ["java", "spring"])
    p = TestClient(app)   # public, unauthenticated
    r = p.post("/api/register/candidate", json={
        "full_name": "Sunita Vermaa", "email": "sunita-dup@local.test",
        "phone": "9866600032", "pan": "SUNIT1234V", "captcha_token": "test-token",
        "consent_data_processing": True, "skills": ["Java"]}, headers=HOST)
    assert r.status_code == 200, r.text
    revs = _reviews(c, status="pending")
    assert len(revs) == 1 and revs[0]["matched_candidate_id"] == first


def test_merge_repoints_archives_and_retires(env):
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    c = TestClient(app); _login(c, RECRUITER)
    survivor = _mk_cand(c, "Anil Mehta", "9866600041", ["python", "aws"])
    loser = _mk_cand(c, "Anil Mehtaa", "9866600042", ["python"])     # → pending review
    rv = _reviews(c, status="pending")[0]
    assert rv["candidate_id"] == loser and rv["matched_candidate_id"] == survivor

    # jobs/applications built directly: job1 loser-only; job2 BOTH (loser further along)
    j1 = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="J1")
    j2 = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="J2")
    db.add_all([j1, j2]); db.flush()
    a1 = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=j1.id,
                     candidate_id=uuid.UUID(loser), stage="screening")
    a2_surv = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=j2.id,
                          candidate_id=uuid.UUID(survivor), stage="applied")
    a2_loser = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=j2.id,
                           candidate_id=uuid.UUID(loser), stage="client_round_1")
    v = Vendor(tenant_id=sps.id, business_unit_id="STAFFING", name="Dedup Vendor")
    db.add_all([a1, a2_surv, a2_loser, v]); db.flush()
    vs = VendorSubmission(tenant_id=sps.id, business_unit_id="STAFFING", vendor_id=v.id,
                          candidate_id=uuid.UUID(loser))
    db.add(vs); db.commit()
    ids = dict(a1=a1.id, a2s=a2_surv.id, a2l=a2_loser.id, vs=vs.id)

    m = c.post(f"/api/candidates/dup-reviews/{rv['id']}/merge", headers=HOST)
    assert m.status_code == 200, m.text
    merge = m.json()["merge"]
    assert merge["survivor"] == survivor and merge["loser"] == loser
    assert str(ids["a1"]) in merge["applications_repointed"]
    assert str(ids["a2l"]) in merge["applications_archived"]

    db.expire_all()
    a1r = db.get(Application, ids["a1"])
    a2sr = db.get(Application, ids["a2s"])
    a2lr = db.get(Application, ids["a2l"])
    vsr = db.get(VendorSubmission, ids["vs"])
    lr = db.get(Candidate, uuid.UUID(loser))
    assert str(a1r.candidate_id) == survivor and a1r.deleted_at is None       # repointed
    assert a2sr.stage == "client_round_1" and a2sr.deleted_at is None              # adopted stage
    assert str(a2lr.candidate_id) == loser and a2lr.deleted_at is not None    # archived in place
    assert str(vsr.candidate_id) == survivor                                  # vendor repointed
    assert lr.deleted_at is not None and lr.phone_bidx is None and lr.pan_bidx is None

    # timeline cross-links on both sides; review closed
    tl_s = c.get(f"/api/candidates/{survivor}/timeline", headers=HOST,
                 params={"event_type": "Merged"}).json()
    tl_l = c.get(f"/api/candidates/{loser}/timeline", headers=HOST,
                 params={"event_type": "MergedInto"}).json()
    assert len(tl_s) == 1 and tl_s[0]["payload"]["merged_from"] == loser
    assert len(tl_l) == 1 and tl_l[0]["payload"]["merged_into"] == survivor
    assert _reviews(c, status="merged")[0]["id"] == rv["id"]
    db.close()


def test_dismiss_keeps_both(env):
    c = TestClient(app); _login(c, RECRUITER)
    a = _mk_cand(c, "Kiran Rao", "9866600051", ["react"])
    b = _mk_cand(c, "Kiran Raoo", "9866600052", ["React", "node"])
    rv = _reviews(c, status="pending")[0]
    d = c.post(f"/api/candidates/dup-reviews/{rv['id']}/dismiss", headers=HOST)
    assert d.status_code == 200 and d.json()["status"] == "dismissed"
    db = get_sessionmaker()()
    for cid in (a, b):
        assert db.get(Candidate, uuid.UUID(cid)).deleted_at is None   # both remain
    db.close()
    # replaying an already-decided review → 409
    again = c.post(f"/api/candidates/dup-reviews/{rv['id']}/merge", headers=HOST)
    assert again.status_code == 409 and again.json()["error"]["code"] == "REVIEW_NOT_PENDING"


def test_tenant_isolation(env):
    c = TestClient(app); _login(c, RECRUITER)
    _mk_cand(c, "Isolated Person", "9866600061", ["python"])
    _mk_cand(c, "Isolated Persoon", "9866600062", ["python"])
    rv = _reviews(c, status="pending")[0]

    db = get_sessionmaker()()
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB5")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB5", slug="testb5", name="Tenant B5"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
    ub = _mk_user(db, tb, "dedup-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb5.spstechnosoft.com"}
    try:
        cb = TestClient(app); _login(cb, "dedup-b@local.test", B_HOST)
        assert cb.get("/api/candidates/dup-reviews", headers=B_HOST).json() == []
        r = cb.post(f"/api/candidates/dup-reviews/{rv['id']}/merge", headers=B_HOST)
        assert r.status_code == 404, "LEAK: tenant B acted on tenant A's review"
    finally:
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit(); db.close()


def test_client_session_403_on_all_endpoints(env):
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Dedup ClientCo")
    db.add(client); db.flush()
    u = User(tenant_id=sps.id, email="dedup-client@local.test",
             password_hash=PasswordHasher().hash(PW), full_name="DC", status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id, status="active"))
    db.commit()
    try:
        c = TestClient(app); _login(c, "dedup-client@local.test")
        assert c.get("/api/candidates/dup-reviews", headers=HOST).status_code == 403
        assert c.post("/api/candidates/dup-reviews/1/merge", headers=HOST).status_code == 403
        assert c.post("/api/candidates/dup-reviews/1/dismiss", headers=HOST).status_code == 403
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.execute(delete(Client).where(Client.id == client.id))
        db.commit(); db.close()
