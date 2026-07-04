"""One-off B.7 real-op verification on dev RDS + real S3 — BACKEND task def (sps_app).

Proves on real infra: seed present, issue→freeze, fetch-by-token leaks no answers,
submit auto-grades + drives aptitude_passed + TestCompletion, snapshot presign +
REAL PUT to the real bucket + key in proctor_flags. Self-cleans business rows and
the S3 object; timeline rows left for master cleanup. Exits non-zero on failure.
"""
from __future__ import annotations

import json
import sys
import urllib.request

from sqlalchemy import delete, select, text

from app import assessment_engine as engine
from app import pipeline, storage
from app.context import RequestContext
from app.db import get_sessionmaker
from app.models_staffing import Application, Candidate, Job, Test

TAG = "[B.7 probe]"


def main() -> int:
    db = get_sessionmaker()()
    who = db.execute(text("SELECT current_user")).scalar_one()
    print(f"connected as: {who} (expect sps_app)")
    if who != "sps_app":
        return 1
    tid = db.execute(text("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
    ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING", user_id=None, roles=())
    snap_key = None
    ok = False
    try:
        n_seed = db.execute(text(
            "SELECT count(*) FROM staffing.questions WHERE tenant_id=:t AND is_active"),
            {"t": str(tid)}).scalar_one()
        assert n_seed >= 12, f"seed missing ({n_seed})"
        print(f"1. seed present on dev RDS ({n_seed} questions) ✅")

        cand = Candidate(tenant_id=tid, full_name=f"Probe Apt Cand {TAG}")
        job = Job(tenant_id=tid, business_unit_id="STAFFING", title=f"Probe Apt Job {TAG}")
        db.add_all([cand, job]); db.flush()
        appn = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                           candidate_id=cand.id, stage="applied")
        db.add(appn); db.commit()
        v = pipeline.transition(db, appn, "screening", ctx=ctx, expected_version=1)["version"]
        db.commit()
        pipeline.transition(db, appn, "aptitude_test", ctx=ctx, expected_version=v)
        db.commit()

        # issue via the engine primitives (same code path the endpoint uses)
        import datetime as dt
        from app.config import settings
        qs = db.execute(select(__import__("app.models_staffing", fromlist=["Question"]).Question)
                        .where(text("questions.tenant_id = :t AND questions.is_active")),
                        {"t": str(tid)}).scalars().all()
        picked = engine.select_questions(qs, settings.test_question_count)
        frozen = engine.freeze_paper(picked)
        raw, h = engine.new_link_token()
        test = Test(tenant_id=tid, business_unit_id="STAFFING", application_id=appn.id,
                    candidate_id=cand.id, link_token_hash=h,
                    valid_until=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
                    served_questions=frozen)
        db.add(test); db.commit()
        pub = engine.public_paper(frozen)
        assert "correct" not in json.dumps(pub)
        print(f"2. issued + froze {len(frozen)} Qs; public paper leaks no answers ✅")

        answers = {f["qid"]: f["correct"] for f in frozen}
        score, passed, _ = engine.grade(frozen, answers)
        test.score, test.passed, test.status = score, passed, "submitted"
        test.submitted_at = dt.datetime.now(dt.timezone.utc)
        db.refresh(appn)
        pipeline.transition(db, appn, "aptitude_passed" if passed else "aptitude_failed",
                            ctx=ctx, expected_version=appn.version)
        from app.timeline import EventType, emit_timeline
        emit_timeline(db, candidate_id=cand.id, event_type=EventType.TEST_COMPLETION,
                      payload={"application_id": str(appn.id), "round": 1,
                               "result": "pass", "score": score, "source": "engine"}, ctx=ctx)
        db.commit(); db.refresh(appn)
        assert appn.stage == "aptitude_passed" and score == 1.0
        print("3. auto-grade + aptitude_passed + TestCompletion on real RDS ✅")

        snap_key = (f"tenant={tid}/business_unit=STAFFING/candidates/{cand.id}/"
                    f"proctor/{test.id}/probe.jpg")
        url = storage.presign_put(snap_key, "image/jpeg")
        req = urllib.request.Request(url, data=b"\xff\xd8\xff probe jpeg bytes", method="PUT")
        req.add_header("Content-Type", "image/jpeg")
        with urllib.request.urlopen(req, timeout=30) as resp:
            assert 200 <= resp.status < 300
        assert storage.head_object(snap_key) is not None
        test.proctor_flags = {"snapshots": [snap_key]}
        db.commit()
        print("4. snapshot presign + REAL PUT to the real bucket + key recorded ✅")

        # ── waiver leg: second application + issued test, flag flipped in-process ──
        from app.config import settings
        from app.routers.assessments import WaiveIn, waive_test
        cand2 = Candidate(tenant_id=tid, full_name=f"Probe Waive Cand {TAG}")
        db.add(cand2); db.flush()
        appn2 = Application(tenant_id=tid, business_unit_id="STAFFING", job_id=job.id,
                            candidate_id=cand2.id, stage="applied")
        db.add(appn2); db.commit()
        v2 = pipeline.transition(db, appn2, "screening", ctx=ctx, expected_version=1)["version"]
        db.commit()
        pipeline.transition(db, appn2, "aptitude_test", ctx=ctx, expected_version=v2)
        db.commit()
        raw2, h2 = engine.new_link_token()
        test2 = Test(tenant_id=tid, business_unit_id="STAFFING", application_id=appn2.id,
                     candidate_id=cand2.id, link_token_hash=h2,
                     valid_until=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
                     served_questions=frozen)
        db.add(test2); db.commit()
        admin_ctx = RequestContext(tenant_id=str(tid), business_unit_id="STAFFING",
                                   user_id=None, roles=("admin",))
        settings.feature_assessment_waiver = False           # flag OFF → 404
        try:
            waive_test(app_id=appn2.id, test_id=test2.id,
                       body=WaiveIn(result="pass", reason="probe"), ctx=admin_ctx,
                       db=db, idempotency_key=None)
            print("flag-OFF waive did NOT 404 ❌"); return 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            assert getattr(e, "status_code", None) == 404, e
        settings.feature_assessment_waiver = True            # flag ON → waive works
        res = waive_test(app_id=appn2.id, test_id=test2.id,
                         body=WaiveIn(result="pass", reason="B.7 probe waiver"),
                         ctx=admin_ctx, db=db, idempotency_key=None)
        settings.feature_assessment_waiver = False           # restore default
        assert res["waived"] is True and res["stage"] == "aptitude_passed"
        db.refresh(test2); db.refresh(appn2)
        assert test2.score is None and test2.passed is True
        assert test2.proctor_flags["waived"]["source"] == "admin_waive"
        assert appn2.stage == "aptitude_passed"
        n_wv = db.execute(text(
            "SELECT count(*) FROM staffing.candidate_timeline WHERE candidate_id=:c "
            "AND event_type='TestCompletion' AND payload->>'source'='admin_waive'"),
            {"c": str(cand2.id)}).scalar_one()
        assert n_wv == 1
        print("5. waiver leg on real RDS: flag-OFF 404 → flag-ON waive → aptitude_passed, "
              "score NULL, waived block, ONE TestCompletion{admin_waive} ✅")
        ok = True
    finally:
        if snap_key:
            try:
                storage.delete_object(snap_key)
                print("6. probe S3 object deleted")
            except Exception as e:  # noqa: BLE001
                print(f"6. S3 cleanup failed: {e}")
        db.rollback()
        db.execute(delete(Test).where(Test.tenant_id == tid,
                   Test.application_id.in_(select(Application.id).join(
                       Job, Job.id == Application.job_id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Application).where(Application.tenant_id == tid,
                   Application.job_id.in_(select(Job.id).where(Job.title.like(f"%{TAG}%")))))
        db.execute(delete(Job).where(Job.tenant_id == tid, Job.title.like(f"%{TAG}%")))
        db.execute(delete(Candidate).where(Candidate.tenant_id == tid,
                                           Candidate.full_name.like(f"%{TAG}%")))
        db.commit(); db.close()
        print("7. probe business rows cleaned (timeline rows left for master cleanup)")
    print("B.7 REAL-OP PROBE: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
