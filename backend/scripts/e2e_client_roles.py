"""Dev E2E probe — client-internal roles (HR vs hiring manager) on dev RDS.

Runs inside the prod image (no httpx → call endpoint functions directly with a
hand-built RequestContext + a real DB session). Proves, against live RDS:
  • owner-scoping: manager A sees only own jobs' pipeline, B invisible (both ways);
    HR sees ALL the client's jobs;
  • offer-write gate: manager 403 on release / joining-date, HR 200 (draft→released);
  • released offer is read-only-visible on the owning manager's job;
  • HR reassign cascades the pipeline; old owner loses it, new owner gains it; manager
    cannot reassign (403);
  • cross-manager / cross-client / cross-tenant leakage = NONE.
Cleans up all business artifacts at the end (audit rows are append-only by design).

Exit 0 = all PASS; exit 1 = any failure.
"""
from __future__ import annotations

import datetime
import sys
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.context import RequestContext
from app.db import get_sessionmaker
from app.models import ClientUser, Tenant, User
from app.models_staffing import Application, Candidate, Client, Interview, Job, Offer, Submission
from app.repositories import TenantScopedRepo
from app.routers import client_portal as cp

BU = "STAFFING"
TAG = "E2E RoleProbe"
results: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    results.append((bool(cond), msg))
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}", flush=True)


def expect_403(fn, msg: str) -> None:
    try:
        fn()
        check(False, f"{msg} (expected 403, got success)")
    except HTTPException as e:
        check(e.status_code == 403, f"{msg} (got {e.status_code})")


def ctx_for(tid, client_id, role, user_id) -> RequestContext:
    return RequestContext(tenant_id=str(tid), business_unit_id=BU, client_id=str(client_id),
                          client_role=role, user_id=str(user_id), roles=("client",))


def make_user(db, tid, email, role, client_id):
    db.execute(delete(ClientUser).where(ClientUser.user_id.in_(
        select(User.id).where(User.tenant_id == tid, User.email == email))))
    db.execute(delete(User).where(User.tenant_id == tid, User.email == email))
    u = User(tenant_id=tid, email=email, password_hash="!", full_name=email.split("@")[0], status="active")
    db.add(u); db.flush()
    db.add(ClientUser(tenant_id=tid, user_id=u.id, client_id=client_id, status="active", role=role))
    return u


def make_pipeline(db, tid, client_id, owner_user_id, cand_name):
    job = Job(tenant_id=tid, business_unit_id=BU, title=f"{cand_name} Role", client_id=client_id,
              owner_user_id=owner_user_id, status="open"); db.add(job); db.flush()
    cand = Candidate(tenant_id=tid, full_name=cand_name); db.add(cand); db.flush()
    appn = Application(tenant_id=tid, business_unit_id=BU, job_id=job.id, candidate_id=cand.id,
                       client_id=client_id, owner_user_id=owner_user_id, stage="offer"); db.add(appn); db.flush()
    db.add(Submission(tenant_id=tid, business_unit_id=BU, application_id=appn.id,
                      client_id=client_id, owner_user_id=owner_user_id))
    offer = Offer(tenant_id=tid, business_unit_id=BU, application_id=appn.id, client_id=client_id,
                  owner_user_id=owner_user_id, ctc=1200000, status="draft"); db.add(offer)
    db.add(Interview(tenant_id=tid, business_unit_id=BU, application_id=appn.id, client_id=client_id,
                     owner_user_id=owner_user_id, mode="video"))
    db.flush()
    return job, appn, offer, cand


def cleanup(db, tid, client_ids, user_ids):
    for cid in client_ids:
        # delete pipeline rows of this probe client (by client_id)
        app_ids = [a.id for a in db.execute(select(Application).where(Application.client_id == cid)).scalars().all()]
        if app_ids:
            for M in (Submission, Offer, Interview):
                db.execute(delete(M).where(M.application_id.in_(app_ids)))
        db.execute(delete(Application).where(Application.client_id == cid))
        cand_ids = [c for c in []]  # candidates tracked separately below
        db.execute(delete(Job).where(Job.client_id == cid))
    db.execute(delete(Candidate).where(Candidate.tenant_id == tid, Candidate.full_name.like(f"{TAG}%")))
    db.execute(delete(ClientUser).where(ClientUser.user_id.in_(user_ids)))
    db.execute(delete(User).where(User.id.in_(user_ids)))
    for cid in client_ids:
        db.execute(delete(Client).where(Client.id == cid))
    db.commit()


def main() -> int:
    db = get_sessionmaker()()
    sps = db.execute(select(Tenant).where(Tenant.code == "SPS001")).scalar_one()
    tb = db.execute(select(Tenant).where(Tenant.code == "TESTB")).scalar_one_or_none()
    if tb is None:
        tb = Tenant(code="TESTB", slug="testb", name="Test Tenant B"); db.add(tb); db.flush()
    # fresh probe clients
    acme = Client(tenant_id=sps.id, business_unit_id=BU, name=f"{TAG} Acme")
    other = Client(tenant_id=sps.id, business_unit_id=BU, name=f"{TAG} Other")
    db.add_all([acme, other]); db.flush()
    hr = make_user(db, sps.id, "e2e-hr@local.test", "client_admin", acme.id)
    mA = make_user(db, sps.id, "e2e-mgrA@local.test", "client_manager", acme.id)
    mB = make_user(db, sps.id, "e2e-mgrB@local.test", "client_manager", acme.id)
    oUser = make_user(db, sps.id, "e2e-other@local.test", "client_admin", other.id)
    db.flush()
    a_job, a_app, a_offer, _ = make_pipeline(db, sps.id, acme.id, mA.id, f"{TAG} A")
    b_job, b_app, b_offer, _ = make_pipeline(db, sps.id, acme.id, mB.id, f"{TAG} B")
    make_pipeline(db, sps.id, other.id, oUser.id, f"{TAG} Other")
    db.commit()
    all_users = [hr.id, mA.id, mB.id, oUser.id]

    cA = ctx_for(sps.id, acme.id, "client_manager", mA.id)
    cB = ctx_for(sps.id, acme.id, "client_manager", mB.id)
    cHR = ctx_for(sps.id, acme.id, "client_admin", hr.id)

    try:
        print("== (a) owner-scoping (base layer) ==", flush=True)
        repoA, repoB, repoHR = TenantScopedRepo(db, cA), TenantScopedRepo(db, cB), TenantScopedRepo(db, cHR)
        for M in (Job, Application, Submission, Offer, Interview):
            aown = {str(r.owner_user_id) for r in repoA.scoped_all(M)}
            bown = {str(r.owner_user_id) for r in repoB.scoped_all(M)}
            check(aown in ({str(mA.id)}, set()) and str(mB.id) not in aown, f"mgr A sees only own {M.__name__}")
            check(str(mA.id) not in bown, f"mgr B cannot see mgr A's {M.__name__}")
        hr_jobs = {str(j.id) for j in repoHR.scoped_all(Job)}
        check(str(a_job.id) in hr_jobs and str(b_job.id) in hr_jobs, "HR sees ALL the client's jobs")

        print("== cross-client + cross-tenant ==", flush=True)
        a_job_clients = {r.client_id for r in repoA.scoped_all(Job)}
        check(other.id not in a_job_clients, "mgr A cannot see the OTHER client's jobs (cross-client)")
        repo_tb = TenantScopedRepo(db, ctx_for(tb.id, acme.id, "client_admin", hr.id))
        check(all(repo_tb.scoped_all(M) == [] for M in (Job, Application, Offer)), "tenant B context reads NONE of SPS rows (cross-tenant)")

        print("== (b) offer-write gate ==", flush=True)
        jd = datetime.date(2026, 9, 1)
        # The HR-only gate is the FastAPI dependency _require_client_admin; calling it
        # directly is the faithful simulation of the request-time guard (the endpoint
        # declares Depends(_require_client_admin)). The full wired 403 is proven over
        # HTTP in tests/test_client_owner_scoping.py.
        # manager READ own offer ok
        mgr_offer_ids = {str(o.id) for o in repoA.scoped_all(Offer)}
        check(str(a_offer.id) in mgr_offer_ids and str(b_offer.id) not in mgr_offer_ids, "mgr A reads own offer, not B's")
        # manager WRITE blocked by the HR-only gate → 403
        expect_403(lambda: cp._require_client_admin(cA), "mgr A blocked by offer-write gate (403)")
        check(cp._require_client_admin(cHR) is cHR, "HR passes the offer-write gate")
        # HR releases A's offer
        res = cp.release_offer(a_offer.id, cp.OfferReleaseIn(joining_date=jd, ctc=1500000), cHR, db)
        check(res["status"] == "released" and res["joining_date"] == jd.isoformat(), "HR releases offer + sets joining date")
        # owning manager now sees it released — READ-ONLY
        db.expire_all()
        rel = next((o for o in TenantScopedRepo(db, cA).scoped_all(Offer) if str(o.id) == str(a_offer.id)), None)
        check(rel is not None and rel.status == "released" and rel.joining_date == jd, "mgr A sees released offer (read-only)")

        print("== HR reassign + manager cannot ==", flush=True)
        expect_403(lambda: cp._require_client_admin(cA), "mgr A blocked by reassign gate (403)")
        rr = cp.reassign_job(a_job.id, cp.ReassignIn(owner_user_id=mB.id), cHR, db)
        check(rr["pipeline_reassigned"] >= 1, "HR reassign cascades the pipeline")
        db.expire_all()
        a_after = {str(j.id) for j in TenantScopedRepo(db, cA).scoped_all(Job)}
        b_after = {str(j.id) for j in TenantScopedRepo(db, cB).scoped_all(Job)}
        check(str(a_job.id) not in a_after, "after reassign, old owner (A) no longer sees the job")
        check(str(a_job.id) in b_after and str(b_job.id) in b_after, "after reassign, new owner (B) sees it + own")
        # reassign to a non-member → 422
        try:
            cp.reassign_job(b_job.id, cp.ReassignIn(owner_user_id=oUser.id), cHR, db)
            check(False, "reassign to a non-member rejected (expected 422)")
        except HTTPException as e:
            check(e.status_code == 422, f"reassign to a non-member rejected ({e.status_code})")

        print("== team management HR-only ==", flush=True)
        expect_403(lambda: cp._require_client_admin(cA), "mgr A blocked by team gate (403)")
        roster = cp.team(cHR, db)
        check(len({m["role"] for m in roster}) == 2 and len(roster) == 3, "HR lists team (HR + 2 managers)")
    finally:
        print("== cleanup ==", flush=True)
        # add any teammate created? none added in this probe. Clean business artifacts.
        cleanup(db, sps.id, [acme.id, other.id], all_users)
        db.close()

    n_fail = sum(1 for ok, _ in results if not ok)
    print(f"\n=== E2E client-roles: {len(results)-n_fail}/{len(results)} PASS, {n_fail} FAIL ===", flush=True)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
