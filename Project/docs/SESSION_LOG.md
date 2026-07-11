# SESSION_LOG — SPS Technosoft build (running slice record)

**Purpose:** a consolidated, per-slice running record of what actually shipped, built
**only from the committed git record + the tracking docs** (not reconstructed from code).
Each entry: slice · commit hash(es) · what shipped (endpoints/files from the diff) ·
dev-probe status · related docs. Where a slice's WHY isn't in the commit/doc record it is
marked thin, not inferred.

**Going forward:** every slice appends its SESSION_LOG entry as part of its commit (the same
echo-the-line discipline as BUILD-LOG). Backfill created 2026-07-09 from `git log`.

> Provenance note: this log covers the **Academy vertical era (A1 → create-2)**. Pre-academy
> staffing work (B-series, F-series) is recorded in BUILD-LOG.md and is not re-transcribed here.
> Cross-refs: `BUILD-LOG.md` (per-slice detail), `DECISIONS.md` (the load-bearing why's),
> `PENDING.md` (deferrals/blockers), `Context/SPS_EDTECH_ACADEMY_BUILD_PLAN_V2.md` (the A1–A10 plan).

---

## Academy backend (A-series)

### A1 — Academy foundation
- **Commits:** `860ad59` (migration 0033 — academy schema, 9 tables + 8-course seed) · `d9c2f50` (FEATURE_ACADEMY flag + gated `/api/academy` router shell) · `cfe73c7` (tests 247→252) · `03b6f18` (dev probe) · `9b34786` (docs)
- **Shipped:** `backend/alembic/versions/0033_academy_foundation.py`, `models_academy.py`, `academy_seed.py`; the `academy` schema (courses, cohorts, students, enrollments, attendance, assignments, assignment_submissions, certificates, payments); `FEATURE_ACADEMY` (404-when-off).
- **Dev-probe:** PASS (`03b6f18` — academy tables + 8-course seed + sps_app PII round-trip).
- **Docs:** BUILD-LOG A1; plan A1.
- **Rationale:** see BUILD-LOG.md / plan — not reconstructed from code.

### A2 — Course catalog + public listing
- **Commits:** `3cae384` (staff CRUD+publish+cohorts + PUBLIC listing) · `0c3b733` (tests 252→257 + gate-matrix public allowlist) · `e4f62e2`,`4c5d837` (docs)
- **Shipped:** `routers/academy.py` — staff course CRUD/publish/cohorts; PUBLIC `GET /api/academy/public/courses` + course detail (published-only, safe-fields allowlist, tenant-by-Host). No migration.
- **Dev-probe:** PASS (per BUILD-LOG A2).
- **Docs:** BUILD-LOG A2; plan A2.

### A3 — Student registration + SEPARATE student auth
- **Commits:** `9a26dce` (migration 0034 — student credentials + Option A consent in shared.consents) · `35113f9` (separate academy-student auth + public registration + emails) · `0ab6653` (docs)
- **Shipped:** `models.py`, `models_academy.py`, `academy_seed.py`, `routers/academy.py`; `POST /register/student`, academy-student auth (distinct cookie `academy_access_token` + distinct secret + `kind` claim; `get_current_student`); 2 B.10 emails (student + admin).
- **Dev-probe:** PASS (per BUILD-LOG A3).
- **Docs:** BUILD-LOG A3; PENDING launch-blockers (minors'/consent); plan A3.

### A4 — Aptitude engine extension (60Q) + academy bank
- **Commits:** `d58ebc1` (migration 0036 — academy aptitude bank + admin-triggered issue) · `270e3ba`, `c618a0b` (dev probe + legs)
- **Shipped:** `routers/academy.py`, `routers/assessments.py`, `academy_seed.py`, `config.py`; parameterized question-count/bank; admin-triggered `issue` → the `/take/{token}` page (reused, 60Q).
- **Dev-probe:** PASS (`270e3ba`,`c618a0b` — staffing-30Q-still-draws + academy issue/take/grade/stamp; no-drop invariant `min(N,count)` + `N>0`).
- **Docs:** BUILD-LOG A4.

### A5 — Tiered discount + enrolment pricing
- **Commits:** `a52b733` (migration 0037 — payment template; money-logic slice)
- **Shipped:** `academy_pricing.py` (`resolve_discount_percent` 20/15/10/0), `routers/take.py` (post-grade stamps enrolment discount + pre-tax final fee), payment-link email (stub).
- **Dev-probe:** per BUILD-LOG A5.
- **Docs:** BUILD-LOG A5; DECISIONS 2026-07-05 (grade advances applied→offered, rests at offered).

*(A6 — payment stub + activation — shipped as part of the A-series; see BUILD-LOG A6. The `_activate_payment` seam A6 introduced is later generalized in 8b-3.)*

---

## Academy student/admin frontend + supporting backend (FE-series)

### FE#1 — Public academy storefront
- **Commits:** `891914e`
- **Shipped:** `frontend/app/(marketing)/academy/{page.tsx, _lib.tsx, courses/[slug]/page.tsx}` — course listing + detail onto the A2 public reads.
- **Dev-probe:** frontend-only, local-verified (no deploy target, C1).
- **Docs:** BUILD-LOG FE#1.

### FE#2 — Public student registration page
- **Commits:** `7b5d08a`
- **Shipped:** `academy/register/page.tsx` — the register form onto `POST /register/student` (id-card presign; consent; minors branch).
- **Dev-probe:** frontend-only, local-verified (C1).
- **Docs:** BUILD-LOG FE#2.

### FE#3 — Student login + portal shell (two-auth)
- **Commits:** `3853c91`
- **Shipped:** `academy/login/page.tsx`, `(student)/academy/student/{layout,page}.tsx`, `lib/auth/session.ts`, `middleware.ts` — academy cookie login; student portal shell; middleware-gated on the academy session.
- **Dev-probe:** frontend-only, local-verified (C1). Key assertion: session persists across reload; student session can't reach `/admin`.
- **Docs:** BUILD-LOG FE#3.

### FE#4 / FE#4b — Student enrolments read + aptitude-invite delivery
- **Commits:** `47bf412` (FE#4) · `5958526` (FE#4b) · `9ea8020` (dev probe) · `4e65ae0` (reconcile docs: FE#1–#3 BUILD-LOG + 3 DECISIONS)
- **Shipped:** `routers/academy.py` — `GET /students/me/enrollments`, `GET /students/me/notifications`; `test_academy_my_enrollments.py`; `(student)/academy/student/page.tsx` (My Academy). FE#4b: the aptitude-invite notification carries the take link in-app.
- **Dev-probe:** PASS (`9ea8020` — staffing S3 blast-radius + academy FE#4/#4b chain + isolation).
- **Docs:** BUILD-LOG FE#4/#4b; DECISIONS 2026-07-05 (presence-only reads; two reads scope on different identities).

### FE#5 — Result/discount view + surface `course.fee`
- **Commits:** `f01ce16` · `4912aed` (dev probe)
- **Shipped:** `routers/academy.py` (adds `course.fee` to `/me/enrollments`), `seed_local_academy.py`, `(student)/academy/student/page.tsx` (result → discount → final).
- **Dev-probe:** PASS (`4912aed` — course.fee surfaced + isolation holds).
- **Docs:** BUILD-LOG FE#5.
- **Rationale:** the LIST (pre-discount) fee wasn't in the payload; added to the read rather than recompute/hardcode on the frontend (commit message).

### FE#6 — Pay (student-initiate)
- **Commits:** `c886006` (backend) · `81aeb6b` (dev probe) · `d7f403b` (frontend)
- **Shipped:** `routers/academy.py` — a student-gated pay-INITIATE endpoint sharing `_activate_payment` with the A6 staff webhook-confirm; `test_academy_student_pay.py`; `(student)/academy/student/pay/page.tsx` (in-flight guard, 409/network-unknown handling).
- **Dev-probe:** PASS (`81aeb6b` — student-initiate pay + real-S3 receipt + isolation-nothing-fired + redelivery + wrong-state).
- **Docs:** BUILD-LOG FE#6.
- **Rationale:** `POST /pay` was staff-gated → a student-gated INITIATE endpoint sharing the same activation seam; split is auth-only (commit message).

### FE#7 — Durable receipt read + `has_receipt`
- **Commits:** `98e0498` (backend) · `439787f` (dev probe) · `197be9c` (probe cleanup fix) · `63455bf` (frontend)
- **Shipped:** `routers/academy.py` — `GET /students/me/enrollments/{id}/receipt` + `has_receipt` on `/me/enrollments`; `test_academy_receipt.py`; dashboard `has_receipt`-gated receipt download.
- **Dev-probe:** PASS (`439787f` — own receipt real %PDF via presign + has_receipt + isolation 404 + unpaid 404). `197be9c` fixed the probe to capture S3 keys as strings before row deletes (the #7 lesson).
- **Docs:** BUILD-LOG FE#7.

### FE#8a — Admin roster read (staff, cross-student)
- **Commits:** `c6dcd10` (backend) · `3173db4` (dev probe) · `b9b3816` (probe rewrite, no TestClient in prod image) · `4e2cd1a` (frontend)
- **Shipped:** `routers/academy.py` — `GET /academy/enrollments` (roster, filters status/course/cohort) + `GET /academy/enrollments/{id}` (detail); staff-gated + tenant/BU-scoped; UNMASKED identity, phone_enc/pan_enc EXCLUDED; `test_academy_roster.py`; `(admin)/admin/academy/enrollments/{page, [id]/page}.tsx`.
- **Dev-probe:** PASS (`3173db4`/`b9b3816` — unmasked + phone/pan absent + flag-off 404 + student 401 + client 403).
- **Docs:** BUILD-LOG FE#8a.

---

## Staff mutation surface (8b-series)

### 8b-1 — Enrolment transition machine
- **Commits:** `055bdbc` · `e51e218` (dev probe)
- **Shipped:** `academy_transitions.py` (new — `transition()` single authority; system/manual-tagged edge table; terminal-set guard; emits `academy.enrollment.transition` audit); refactored the two production writers (`routers/take.py` grade, `routers/academy.py` pay `_activate_payment`) through it; `test_academy_transitions.py`. NO migration.
- **Dev-probe:** PASS (`e51e218` — grade+pay route through transition() + emit the status audit; both audits on pay).
- **Docs:** BUILD-LOG 8b-1; DECISIONS (this reconciliation). PENDING A4b (create-path gap flagged here).

### 8b-2 — Manual status-move endpoint
- **Commits:** `a755165` · `a22b3fe` (dev probe)
- **Shipped:** `routers/academy.py` — `POST /academy/enrollments/{id}/status {to_state, reason}`, staff-gated + tenant/BU-scoped, DELEGATES legality to `transition(kind="manual")`; `test_academy_status_move.py`. NO migration.
- **Dev-probe:** PASS (`a22b3fe` — manual move w/ staff-actor audit + machine-delegated →active 409).
- **Docs:** BUILD-LOG 8b-2; DECISIONS (this reconciliation).

### 8b-3 — Fee-waive (generalize the activation seam)
- **Commits:** `c543170` (migration 0041 — waiver email template) · `28031e8` (dev probe)
- **Shipped:** `routers/academy.py` — split the activation seam into a shared core + payment path + waiver path; `POST /academy/enrollments/{id}/waive {reason}`; `academy_seed.py` (waiver template); `test_academy_waive.py`; `(student)/academy/student/page.tsx` (dashboard 'waived' branch). Migration 0041 (data-only).
- **Dev-probe:** PASS (`28031e8` — waiver no-Payment-row + coherence + payment-path-unchanged + one-entry-point).
- **Docs:** BUILD-LOG 8b-3; DECISIONS (this reconciliation).

### 8b frontend — admin status-move + waive controls
- **Commits:** `6430167`
- **Shipped:** `(admin)/admin/academy/enrollments/[id]/page.tsx` — state-aware action controls mirroring the machine's legal edges; ActionModal (reason required, in-flight guard); no "activate" control.
- **Dev-probe:** frontend-only, local-verified (C1). State-aware gating verified functionally against the endpoints.
- **Docs:** BUILD-LOG 8b frontend.

---

## Enrolment CREATE path (create-series)

### create-1 — Apply endpoint + public applyable-cohorts read
- **Commits:** `259b654` · `2f5bbd0` (dev probe)
- **Shipped:** `routers/academy.py` — `POST /academy/students/me/enrollments {course_id, cohort_id}` (student-gated, own-scoped, published-course + applyable-cohort validation, course-level dedup, UNIQUE-catch → 409) + `GET /academy/public/courses/{slug}/cohorts`; `test_academy_apply.py`. The first PRODUCTION creator of an 'applied' enrolment. NO migration.
- **Dev-probe:** PASS (`2f5bbd0` — full chain from a real applied + dedup + double-submit + applyable filter).
- **Docs:** BUILD-LOG CREATE-1; PENDING A4b marked CLOSED; DECISIONS (this reconciliation).

## Infra / cross-domain (C1-series)

### C1-1 — Cross-domain auth hardening (cookies + CORS)
- **Commits:** (this commit) — code + terraform env; dev-probed on the live service.
- **Shipped:** `app/cookies.py` (new — the single session-cookie seam: env-driven Domain/SameSite/
  Secure, SameSite=None forces Secure, delete echoes Domain/Path); `routers/auth.py` + `routers/
  academy.py` (staff + academy login/logout route through it); `main.py` (env-driven credentialed
  CORS — explicit origins, never wildcard); `config.py` (COOKIE_DOMAIN/COOKIE_SAMESITE/
  CORS_ALLOWED_ORIGINS); `Project/ecs.tf` + `variables.tf` (dev-shape env: `.spstechnosoft.com` /
  none / Secure / `var.frontend_origin`). Frontend unchanged (credentials:'include' already present).
- **Inert-when-unset:** local (envs unset) stays byte-identical (Lax/host-only/insecure, no CORS).
- **Dev-probe:** the deploy sets the live dev task-def env (terraform apply) — the live login
  Set-Cookie carries Domain=.spstechnosoft.com; SameSite=None; Secure; HttpOnly, the cookie
  round-trips (login→/me 200), and a credentialed preflight from the frontend origin is allowed.
- **Docs:** BUILD-LOG C1-1; DECISIONS 2026-07-11 (C1 staging shape); PENDING C1 slice-1 done.
- **NO migration** (config/headers; dev 0041).

### create-2 — course_id envelope + storefront apply wiring
- **Commits:** `9644ca6` (backend envelope) · `288ad0a` (dev probe) · `45f53c3` (frontend)
- **Shipped:** `routers/academy.py` — `GET /public/courses/{slug}/cohorts` now returns `{course_id, cohorts:[...]}`; `test_academy_apply.py`; frontend `academy/courses/[slug]/page.tsx` (session-aware ApplyPanel), `login/page.tsx` (`?next`), `register/page.tsx` (threads `next`). NO migration.
- **Dev-probe:** PASS (`288ad0a` — course_id envelope + round-trip into apply + published gate). Frontend local-verified (C1); next-survival trace + clean build + functional loop.
- **Docs:** BUILD-LOG create-2; DECISIONS (this reconciliation).
