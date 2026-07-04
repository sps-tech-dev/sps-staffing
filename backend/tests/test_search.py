"""B.4 candidate search: setweight ranking, websearch grammar, filters, trigger
maintenance, erasure interplay (erased → search_doc NULL + absent), isolation, gates,
PII masking."""
from __future__ import annotations

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.crypto import blind_index
from app.db import get_sessionmaker
from app.main import app
from app.models import BusinessUnit, ClientUser, Consent, DpdpRequest, Membership, Tenant, User
from app.models_staffing import (
    Application, Candidate, CandidateDupReview, CandidateTimeline, Client, Job,
)

HOST = {"host": "spstechnosoft.com"}
PW = "SearchLocal!123"
RECRUITER = "search-rec@local.test"


def _mk_user(db, tenant, email, roles):
    # robust against leftovers from a previously-crashed run: memberships + dpdp first
    old = db.execute(select(User).where(User.tenant_id == tenant.id,
                                        User.email == email)).scalar_one_or_none()
    if old is not None:
        db.execute(delete(DpdpRequest).where(DpdpRequest.subject_user_id == old.id))
        db.execute(delete(Membership).where(Membership.user_id == old.id))
        db.execute(delete(User).where(User.id == old.id))
    u = User(tenant_id=tenant.id, email=email, password_hash=PasswordHasher().hash(PW),
             full_name="Search Tester", status="active")
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
    db.execute(delete(CandidateDupReview).where(CandidateDupReview.tenant_id == sps.id))
    db.execute(delete(CandidateTimeline).where(CandidateTimeline.tenant_id == sps.id))
    db.execute(delete(Consent).where(Consent.tenant_id == sps.id))
    db.execute(delete(DpdpRequest).where(DpdpRequest.tenant_id == sps.id))
    for M in (Application, Job, Candidate, Client):
        db.execute(delete(M).where(M.tenant_id == sps.id))
    db.execute(delete(Membership).where(Membership.user_id == rec.id))
    db.execute(delete(User).where(User.id == rec.id))
    db.commit(); db.close()


def _login(c, email, host=HOST):
    assert c.post("/api/auth/login", json={"email": email, "password": PW},
                  headers=host).status_code == 200


def _cand(db, sps, name, skills=None, resume=None, exp=None, phone=None):
    c = Candidate(tenant_id=sps.id, full_name=name, skills=skills,
                  resume_text=resume, total_exp=exp,
                  phone_enc=phone, phone_bidx=blind_index(phone))
    db.add(c); db.commit()          # INSERT fires the trigger
    return str(c.id)


def _search(c, **params):
    r = c.get("/api/candidates/search", headers=HOST, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_setweight_ranking_name_over_skill_over_resume(env):
    sps, db = env
    a = _cand(db, sps, "Terraform Anvi")                                 # name (A)
    b = _cand(db, sps, "Bela Rao", skills=["terraform", "aws"])          # skill (B)
    d = _cand(db, sps, "Chirag Shah", resume="5 years of terraform IaC") # resume (C)
    c = TestClient(app); _login(c, RECRUITER)
    got = [r["id"] for r in _search(c, q="terraform")]
    assert got == [a, b, d], f"setweight ranking broken: {got}"


def test_websearch_boolean_and_exclusion(env):
    sps, db = env
    both = _cand(db, sps, "Both Person", skills=["python", "aws"])
    only_py = _cand(db, sps, "Py Person", skills=["python"])
    c = TestClient(app); _login(c, RECRUITER)
    ids = [r["id"] for r in _search(c, q="python AND aws")]
    assert ids == [both]
    ids = [r["id"] for r in _search(c, q="python -aws")]
    assert ids == [only_py]


def test_resume_only_match_appears(env):
    sps, db = env
    r_only = _cand(db, sps, "Resume Only", resume="worked extensively with kafka streams")
    c = TestClient(app); _login(c, RECRUITER)
    assert [r["id"] for r in _search(c, q="kafka")] == [r_only]


def test_structured_filters_narrow(env):
    sps, db = env
    jr = _cand(db, sps, "Junior Dev", skills=["python"], exp=1.5)
    sr = _cand(db, sps, "Senior Dev", skills=["python", "aws"], exp=8)
    c = TestClient(app); _login(c, RECRUITER)
    assert {r["id"] for r in _search(c, skills="python")} == {jr, sr}
    assert [r["id"] for r in _search(c, skills="python,aws")] == [sr]     # @> requires ALL
    assert [r["id"] for r in _search(c, exp_min=5)] == [sr]
    assert [r["id"] for r in _search(c, exp_max=3)] == [jr]
    assert [r["id"] for r in _search(c, q="python", exp_min=5)] == [sr]   # q + filter combine


def test_trigger_refreshes_on_update(env):
    sps, db = env
    cid = _cand(db, sps, "Update Me", skills=["golang"])
    c = TestClient(app); _login(c, RECRUITER)
    assert _search(c, q="rustlang") == []
    cand = db.execute(select(Candidate).where(Candidate.full_name == "Update Me")).scalar_one()
    cand.skills = ["rustlang"]
    db.commit()                                        # UPDATE fires the trigger
    assert [r["id"] for r in _search(c, q="rustlang")] == [cid]


def test_erased_candidate_not_searchable_and_doc_null(env):
    sps, db = env
    subj = _mk_user(db, sps, "search-erase@local.test", ["candidate"])
    cid = _cand(db, sps, "Erase Findable", skills=["cobol"])
    cand = db.get(Candidate, __import__("uuid").UUID(cid))
    cand.email = "search-erase@local.test"             # link to the erasure subject
    db.commit()
    c = TestClient(app); _login(c, RECRUITER)
    assert [r["id"] for r in _search(c, q="cobol")] == [cid]

    sc = TestClient(app); _login(sc, "search-erase@local.test")
    assert sc.post("/api/privacy/erase", headers=HOST).status_code == 200

    assert _search(c, q="cobol") == [], "erased candidate still searchable"
    doc = db.execute(text("SELECT search_doc FROM staffing.candidates WHERE id=:i"),
                     {"i": cid}).scalar_one()
    assert doc is None, "trigger re-populated search_doc on the erasure UPDATE"
    # cleanup order matters: dpdp_requests FKs the subject user
    db.execute(delete(DpdpRequest).where(DpdpRequest.subject_user_id == subj.id))
    db.execute(delete(Membership).where(Membership.user_id == subj.id))
    db.execute(delete(User).where(User.id == subj.id)); db.commit()


def test_tenant_isolation(env):
    sps, db = env
    _cand(db, sps, "Tenant A Scala Person", skills=["scala"])
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB6")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB6", slug="testb6", name="Tenant B6"); db.add(tb); db.flush()
        db.add(BusinessUnit(tenant_id=tb.id, code="STAFFING", name="Staffing")); db.flush()
    db.add(Candidate(tenant_id=tb.id, full_name="Tenant B Scala Person", skills=["scala"]))
    db.commit()
    ub = _mk_user(db, tb, "search-b@local.test", ["recruiter"])
    B_HOST = {"host": "testb6.spstechnosoft.com"}
    try:
        ca = TestClient(app); _login(ca, RECRUITER)
        names = {r["full_name"] for r in _search(ca, q="scala")}
        assert names == {"Tenant A Scala Person"}, f"LEAK: {names}"
        cb = TestClient(app); _login(cb, "search-b@local.test", B_HOST)
        r = cb.get("/api/candidates/search", headers=B_HOST, params={"q": "scala"})
        assert {x["full_name"] for x in r.json()} == {"Tenant B Scala Person"}
    finally:
        db.execute(delete(Candidate).where(Candidate.tenant_id == tb.id))
        db.execute(delete(Membership).where(Membership.user_id == ub.id))
        db.execute(delete(User).where(User.id == ub.id))
        db.execute(delete(BusinessUnit).where(BusinessUnit.tenant_id == tb.id))
        db.execute(delete(Tenant).where(Tenant.id == tb.id)); db.commit()


def test_gates_and_masking(env):
    sps, db = env
    _cand(db, sps, "Masked Person", skills=["python"], phone="9844400001")
    # unauth → 401
    assert TestClient(app).get("/api/candidates/search", headers=HOST).status_code == 401
    # client session → 403
    client = Client(tenant_id=sps.id, business_unit_id="STAFFING", name="Search ClientCo")
    db.add(client); db.flush()
    u = User(tenant_id=sps.id, email="search-client@local.test",
             password_hash=PasswordHasher().hash(PW), full_name="SC", status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=sps.id, user_id=u.id, client_id=client.id, status="active"))
    db.commit()
    try:
        cc = TestClient(app); _login(cc, "search-client@local.test")
        assert cc.get("/api/candidates/search", headers=HOST).status_code == 403
        # masking: staff card carries presence flags only, never PII values
        cs = TestClient(app); _login(cs, RECRUITER)
        card = _search(cs, q="python")[0]
        assert card["has_phone"] is True
        assert "phone" not in card and "pan" not in card and "email" not in card
        assert "9844400001" not in str(card)
    finally:
        db.execute(delete(ClientUser).where(ClientUser.user_id == u.id))
        db.execute(delete(User).where(User.id == u.id))
        db.execute(delete(Client).where(Client.id == client.id)); db.commit()
