"""F3a: candidate↔user linkage — the three merge cases (esp. both-different→flag,
no silent data loss), registration auto-link, /me/applications live stages, real
/me/overview with graceful null-linkage zeros."""
from __future__ import annotations

import uuid

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.main import app
from app.models import (
    AuditLog, BusinessUnit, ClientUser, Consent, Membership, Tenant, User,
)
from app.models_staffing import (
    Application, Candidate, CandidateDupReview, CandidateTimeline, Client, Interview,
    Job, Offer,
)

HOST = {"host": "spstechnosoft.com"}
PW = "MeLocal!123"
STAFF = "me-staff@local.test"


def _mk_user(db, tenant, email, roles):
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(ClientUser).where(ClientUser.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Me Tester", status="active")
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
    staff = _mk_user(db, sps, STAFF, ["recruiter"])
    made_users = [staff]
    yield sps, db, made_users
    db.execute(delete(CandidateDupReview).where(CandidateDupReview.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    for M in (Interview, Offer, Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    for u in made_users:
        db.execute(delete(Membership).where(Membership.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
    db.commit(); db.close()


def _login(c, email):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=HOST).status_code == 200


def _merge_setup(db, sps, survivor_user=None, loser_user=None):
    surv = Candidate(tenant_id=sps.id, full_name="Me Surv",
                     user_id=survivor_user.id if survivor_user else None)
    loser = Candidate(tenant_id=sps.id, full_name="Me Loser",
                      user_id=loser_user.id if loser_user else None)
    db.add_all([surv, loser]); db.flush()
    review = CandidateDupReview(tenant_id=sps.id, business_unit_id="STAFFING",
                                candidate_id=loser.id, matched_candidate_id=surv.id,
                                match_type="fuzzy", score=0.9, status="pending")
    db.add(review); db.commit()
    return surv, loser, review


def _do_merge(review_id):
    c = TestClient(app); _login(c, STAFF)
    r = c.post(f"/api/candidates/dup-reviews/{review_id}/merge", headers=HOST)
    assert r.status_code == 200, r.text
    return r


def test_merge_survivor_keeps_own_link(env):
    sps, db, users = env
    u = _mk_user(db, sps, "me-surv-u@local.test", ["candidate"]); users.append(u)
    surv, loser, review = _merge_setup(db, sps, survivor_user=u)
    _do_merge(review.id)
    db.refresh(surv)
    assert surv.user_id == u.id


def test_merge_loser_only_link_moves(env):
    sps, db, users = env
    u = _mk_user(db, sps, "me-loser-u@local.test", ["candidate"]); users.append(u)
    surv, loser, review = _merge_setup(db, sps, loser_user=u)
    _do_merge(review.id)
    db.refresh(surv)
    assert surv.user_id == u.id, "loser-only login did not move to survivor"


def test_merge_both_different_flags_no_data_loss(env):
    sps, db, users = env
    u1 = _mk_user(db, sps, "me-u1@local.test", ["candidate"]); users.append(u1)
    u2 = _mk_user(db, sps, "me-u2@local.test", ["candidate"]); users.append(u2)
    surv, loser, review = _merge_setup(db, sps, survivor_user=u1, loser_user=u2)
    _do_merge(review.id)
    db.refresh(surv); db.refresh(loser)
    # survivor keeps ITS login; loser RETAINS its user_id (soft-deleted, not nulled)
    assert surv.user_id == u1.id
    assert loser.user_id == u2.id and loser.deleted_at is not None
    # the conflict is durably flagged: dedicated audit row + timeline event
    audit = db.execute(select(AuditLog).where(
        AuditLog.tenant_id == sps.id,
        AuditLog.action == "candidate.merge_link_conflict")).scalars().all()
    assert len(audit) == 1
    assert audit[0].after["loser_user_id"] == str(u2.id)
    tl = db.execute(select(CandidateTimeline).where(
        CandidateTimeline.tenant_id == sps.id,
        CandidateTimeline.event_type == "MergeLinkConflict")).scalars().all()
    assert len(tl) == 1 and tl[0].payload["survivor_user_id"] == str(u1.id)


def test_registration_autolink_when_login_exists(env):
    sps, db, users = env
    u = _mk_user(db, sps, "me-reg@local.test", ["candidate"]); users.append(u)
    c = TestClient(app)
    r = c.post("/api/register/candidate", headers=HOST, json={
        "full_name": "Me Reg", "email": "me-reg@local.test",
        "phone": "+919911224488", "pan": "MEPAN1234R",
        "captcha_token": "local-test-token", "consent_data_processing": True})
    assert r.status_code == 200, r.text
    cand = db.execute(select(Candidate).where(Candidate.tenant_id == sps.id,
                                              Candidate.email == "me-reg@local.test")).scalar_one()
    assert cand.user_id == u.id, "registration did not auto-link the existing login"


def test_me_surface_linked_and_unlinked(env):
    sps, db, users = env
    u = _mk_user(db, sps, "me-cand@local.test", ["candidate"]); users.append(u)
    u2 = _mk_user(db, sps, "me-bare@local.test", ["candidate"]); users.append(u2)
    cand = Candidate(tenant_id=sps.id, full_name="Me Cand", user_id=u.id)
    db.add(cand); db.flush()
    job = Job(tenant_id=sps.id, business_unit_id="STAFFING", title="Me Job")
    db.add(job); db.flush()
    appn = Application(tenant_id=sps.id, business_unit_id="STAFFING", job_id=job.id,
                       candidate_id=cand.id, stage="client_round_1")
    db.add(appn); db.flush()
    db.add(Interview(tenant_id=sps.id, business_unit_id="STAFFING",
                     application_id=appn.id, mode="video"))
    db.add(Offer(tenant_id=sps.id, business_unit_id="STAFFING", application_id=appn.id,
                 ctc=900000, status="draft"))
    db.commit()
    # linked: live stages + real counts
    c = TestClient(app); _login(c, "me-cand@local.test")
    apps = c.get("/api/me/applications", headers=HOST).json()
    assert len(apps) == 1 and apps[0]["stage"] == "client_round_1" and apps[0]["job"] == "Me Job"
    ov = c.get("/api/me/overview", headers=HOST).json()
    assert ov["applications"] == 1 and ov["interviews"] == 1 and ov["offers"] == 1
    assert ov["recent"][0]["stage"] == "client_round_1"
    # unlinked login: zeros/empty, NOT an error
    c2 = TestClient(app); _login(c2, "me-bare@local.test")
    r = c2.get("/api/me/applications", headers=HOST)
    assert r.status_code == 200 and r.json() == []
    r2 = c2.get("/api/me/overview", headers=HOST)
    assert r2.status_code == 200 and r2.json()["applications"] == 0
