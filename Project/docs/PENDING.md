# Outstanding / Deferred — DO NOT SKIP

**This file is the single source of truth for everything deferred in the SPS build.**
Claude Code must read it at the start of any session before assuming work is "done,"
and must not silently skip any item here. When an item is resolved, move it to
**Resolved** at the bottom with the date. When new deferrals happen, add them here
(with: what / why deferred / what it blocks / trigger to pick up).

Last refreshed: 2026-06-28 (after client-internal roles / owner-scoped jobs — Task 7).

---

## A. Blocks taking REAL users (launch-critical — pair these before any real signup/demo)

### A1. DPDP / legal copy — all `[LEGAL COPY TBD]` (STOP-3)
- **What:** Real wording for: candidate-registration consent text, the DPDP consent
  notices (`data_processing` / `marketing` / `cookies` in `app/routers/privacy.py` →
  `POLICY_TEXT`), the privacy policy, the terms of service, and the CLIENT registration consent notice. All are placeholders.
- **Why deferred:** legal content must come from the user/legal, not be invented (STOP-3).
- **Blocks:** taking ANY real candidate or user — DPDP requires informed consent for
  PAN collection. Registration is functionally live but must not onboard real people.
- **Trigger:** user/legal supplies wording → replace placeholders → **bump `POLICY_VERSION`**
  (`app/routers/privacy.py`) → remove the "Draft notices" banners.

### A2. hCaptcha real keys (STOP-4) — scaffold BUILT (inert/test mode); keys still needed
- **What:** App mechanism wired (`app/captcha.py`: real `siteverify` only when `HCAPTCHA_SECRET`
  non-empty; else test mode). **Terraform scaffold now APPLIED** (`Project/hcaptcha.tf`):
  Secrets Manager `sps-shared-dev-hcaptcha` exists but is seeded **EMPTY** (`lifecycle
  ignore_changes` so the real value is never clobbered); execution-role GetSecretValue; backend
  task def wires `HCAPTCHA_SITEKEY` (env, empty) + `HCAPTCHA_SECRET` (from secret, empty). Empty ⇒
  app stays in **test mode** (verified live: service healthy, registration accepts test token).
- **Why deferred:** real keys need an hCaptcha account — user's STOP-4 decision.
- **Blocks:** real candidate signups (bot protection is test mode = effectively open). **Pairs with
  A1 (legal copy)** — BOTH must be resolved before real registration opens.
- **Trigger / go-live steps (all out-of-band):** (1) create an hCaptcha account → public site key +
  secret; (2) `aws secretsmanager put-secret-value --secret-id sps-shared-dev-hcaptcha
  --secret-string '{"secret":"<REAL>"}'` (**never in git/TF**); (3) set `var.hcaptcha_sitekey` to the
  public site key (+ apply, pinning `-var backend_image_tag=<live>` per C3); (4) redeploy so tasks
  pick up the real secret.

### A3. Deployed-dev real login (STOP-4)
- **What:** `dev-api` mints no tokens (founder is `invited`; JWT secrets are unexercised
  defaults). Local loop does real logins meanwhile.
- **Why deferred:** needs JWT secret → Secrets Manager + ECS task-def `secrets` wiring +
  execution-role IAM grant + `COOKIE_SECURE=true` + an activated dev user (STOP-4).
- **Blocks:** clickable login on `dev-api`; any UAT/stakeholder demo on dev.
- **Trigger:** before any UAT/stakeholder demo on dev-api.

---

## B. DPDP / compliance follow-ups

### B1. DPDP erasure engine — STAGE 1 BUILT; auto-purge STUBBED pending legal retention periods
- **Status (2026-06-28):** **Stage 1 BUILT + live** — disable-on-request (soft-delete) → approval
  gate (auto-approve normal; `legal_hold` exempt + manual approval) → **anonymize** irreversibly
  (incl. **clearing `*_bidx` blind indexes**) → retain de-identified records → append-only
  `dpdp.erasure_executed` audit. Code: `app/erasure.py`, `app/routers/privacy.py` (erase),
  `app/routers/admin.py` (`/erasure-requests` list/approve/reject/legal-hold), migration `0010`
  (`legal_hold` + state machine). Model ratified in DECISIONS.
- **AUTO-PURGE = INERT STUB:** `erasure.auto_purge_due_requests` reads `settings.dpdp_retention_days`
  (deliberately `None`) and **deletes NOTHING** (logs "pending legal retention-period determination").
  **Do NOT implement a timed hard-delete on a guessed period.** Activation is gated on the legal
  questions below.
- **Remaining OPEN legal questions — gate auto-purge activation + full real-user go-live** (Q2
  delete-vs-anonymize and Q4 users were RATIFIED → hybrid anonymize/disable; the rest remain open;
  each trigger = "decide before activating auto-purge / opening real erasure"):
  - **Q1 Retention floor:** which records/periods are legally retention-required (GST/TDS, placement/
    invoice, statutory) and must survive — and for how long (the number auto-purge needs)?
  - **Q3 audit_logs identifiers:** retaining `actor_id`/`entity_id` in the immutable log is acceptable
    under DPDP, or must we pseudonymize identifiers at write-time going forward?
  - **Q5 Legal-hold rule:** what defines an account under hold/dispute (so `under_legal_hold` can
    return True instead of the current always-False stub)?
  - **Q6 SLA:** required fulfilment SLA (e.g. 30 days) + is a human approval gate mandatory for normal
    erasures (today normal = auto-approved)?
  - **Q7 Consent records:** retain consent history (proof of lawful basis) after erasure, or purge?
- **Reference — PII data map (what an erasure must reach):** `staffing.candidates` (full_name, email,
  `phone_enc`/`pan_enc`, **`phone_bidx`/`pan_bidx`** pseudonymous identifiers, skills, `resume_s3_key`,
  `source`, `search_doc`, soft-delete `deleted_at`); `staffing.applications` (candidate↔job linkage +
  placement record); `shared.consents` (subject linkage + consent history); `shared.audit_logs`
  (`actor_id`/`entity_id` linkage + `before`/`after` JSONB; **append-only — `sps_app` physically
  CANNOT delete → audit erasure is impossible-by-design**); `shared.users` (email/full_name/
  password_hash — if the person has a login); **S3 resume objects** under `resume_s3_key`;
  `shared.dpdp_requests` (the erasure-request record itself — retain as proof).
- **Retained-untouched (Stage 1):** `consents`, `audit_logs` (append-only — can't delete), `dpdp_requests`;
  `applications` retained de-identified transitively. **S3 resume objects:** delete is wired but inert
  (no upload code/keys yet → no-op; needs `s3:DeleteObject` grant + bucket-cfg fix, see C5).
- **Blocks:** auto-purge activation + full real-user erasure go-live (the Q1/Q3/Q5/Q6/Q7 answers).
- **Trigger:** legal answers the open questions → then activate auto-purge (set retention period +
  implement the timed purge, reviewed before any RDS run) and tighten the legal-hold rule / SLA.

### B2. DPDP export completion — ✅ RESOLVED (see Resolved section)

### B3. audit_logs / consents append-only enforcement — ✅ RESOLVED (see Resolved section)

### B5. Invoicing GST/TDS compliance specifics — await legal confirmation
- **What:** the placement-invoice structure (`staffing.invoices`) is built — the **15% placement
  fee is computed** (SPS business term, configurable per invoice). But **GST and TDS are NOT
  hardcoded**: `gst_percent`/`tds_percent` are NULL by default and tax amounts are computed ONLY
  when a rate is explicitly supplied. No statutory rate, rounding rule, place-of-supply / RCM logic,
  HSN/SAC codes, invoice-numbering format, or retention rule is baked in.
- **Why deferred:** GST/TDS rates + compliance specifics are a legal determination (ties to Q1
  retention floor). Must not guess tax law.
- **Blocks:** issuing compliant real invoices.
- **Trigger:** legal confirms GST/TDS rates + invoice compliance rules → wire them as config
  (per-tenant/region), add invoice numbering + PDF, then enable issuing real invoices.

### B4. Keep PII out of Redis — invariant to uphold (surfaced by the erasure data-map)
- **What:** the export endpoint's Idempotency-Key caching was removed precisely so decrypted PII
  is never written to Redis. Current Redis use (idempotency for consent/register, sessions) holds
  **no PII** (verified). This is an invariant, not a bug.
- **Why tracked:** a future cached/denormalized path could reintroduce PII into Redis (which has no
  field-level encryption and, in dev, no transit encryption) — and Redis is OUTSIDE the erasure cascade.
- **Blocks:** nothing now.
- **Trigger:** any new caching/denormalization of candidate/user data — keep PII out, or include
  that store in the erasure cascade.

---

## C. Infra / deploy / multi-tenancy

### C1. Wildcard subdomain routing + CloudFront + frontend deploy target (STOP-4)
- **What:** the frontend has NO deploy target (verified locally only). Real tenant-subdomain
  routing (`*.spstechnosoft.com`), wildcard ACM cert, CloudFront, and the **Host↔JWT
  `tenant_id` cross-check** (deferred until subdomains exist) all live here.
- **Why deferred:** paid edge infra + not needed for the local dev loop.
- **Blocks:** real multi-tenant subdomain access; a deployed/clickable frontend; the edge
  isolation cross-check.
- **Trigger:** when standing up real tenant subdomains / a hosted frontend. On build, wire
  the Host↔JWT cross-check (→403 on mismatch) and a backend trusted-forwarded-host check.

### C2. Marketing SSG-per-locale for SEO (deferred from F5)
- **What:** marketing i18n is cookie-based (route renders `ƒ` dynamic). SEO wants
  `app/[locale]/` with `hreflang` (static per-locale).
- **Why deferred:** avoided restructuring all routes + the auth middleware for marketing copy.
- **Blocks:** per-locale SEO indexing of the marketing site.
- **Trigger:** when SEO/marketing demands per-locale static pages.

### C3. Terraform `backend_image_tag` decoupled from CI-deployed image (landmine)
- **What:** CI deploys images by git-SHA tag *outside* Terraform; `var.backend_image_tag`
  default lags. A plain `terraform apply` (no `-var`) would **regress the running image**
  to the stale default. Current applies pin `-var "backend_image_tag=<live SHA>"` to avoid it.
- **Why deferred:** pre-existing decoupling; full fix is a design choice.
- **Blocks:** safe `terraform apply` without remembering the `-var`.
- **Trigger:** decide a fix — e.g. a data source for the live image, `lifecycle ignore_changes`
  on the image, or always pin via CI. Until then, ALWAYS pin `-var backend_image_tag=<live>`.

### C4. Backend Terraform lockfile migration
- **What:** switch to `use_lockfile = true`, then delete the `sps-staffing-tflock` DynamoDB table.
- **Why deferred:** housekeeping.
- **Blocks:** nothing functional; removes a legacy lock table.
- **Trigger:** any infra-cleanup pass.

### C5. S3 resume object lifecycle — ✅ RESOLVED 2026-07-04 (B.1; see Resolved section)

---

## D. Product scope not yet built

### D1. Other verticals — Academy (Training/Internship) & Consulting (IT Services) portals
- **What:** only the Staffing vertical is built. Academy + Consulting portals are not.
- **Why deferred:** sequencing — Staffing first.
- **Blocks:** those product lines.
- **Trigger:** when the standing sequence reaches them.

### D11. F1 frontend foundation — resolutions + follow-ups (added 2026-07-04)
- **D5 → RESOLVED (frontend):** the kanban and stage-consuming screens now speak the B.5
  vocabulary (14 forward columns + read-only tail; friendly labels).
- **D4b → RESOLVED:** /employer/* staff tools re-homed to the employee role (they had been
  unreachable by anyone since the client-portal split); linked from the employee nav.
- **kanban optimistic lock → RESOLVED 2026-07-04 (F2):** `version` exposed (F2a, deployed);
  the kanban now posts /transition with expected_version; the PATCH shim is deleted from the
  frontend. (The deprecated backend PATCH endpoint itself can be removed once no other
  consumer exists — candidate for the next backend touch.)
- **candidate portal read surface → RESOLVED 2026-07-04 (F3):** candidates.user_id (0032,
  explicit link), /me/applications, real /me/overview; merge both-different-logins conflicts
  flagged durably. Candidate SELF-APPLY remains a deliberate non-feature (applications are
  staff-placed); if the business ever wants it, that's a new backend decision.
- **E2E-1 → RESOLVED 2026-07-05:** 5 staffing GETs gated (`_require_staff`); the route-smoke
  matrix (which was a silent no-op — enumerated via app.routes past the `_IncludedRouter` wrapper)
  repaired to use `app.openapi()` + a fail-closed gate-matrix (candidate/client must 403 on staff
  GETs) + route-count floors. Commit `3964fcd`, dev-proven.
- **E2E-3 → RESOLVED 2026-07-05:** session-scoped autouse fixture (tests/conftest.py) seeds the
  12-question aptitude bank deterministically; suite proven green from an empty DB. Test-only,
  no deploy. (Local dev DB no longer carries the migration SAMPLE bank after the fresh-clone
  simulation — irrelevant to tests now; dev RDS seed untouched.)
- **E2E-2 (minor, tracked): no write API for `client.fee_percent`** — settable only via DB
  (ClientIn lacks it; no PATCH /clients). Fine while fees are seeded, but the client-fee override
  from B.9 has no UI/endpoint path. Fold into a future commercial-admin slice.
- **F4 → DONE 2026-07-04**; **F5 → DONE 2026-07-05**; **F6 → DONE 2026-07-05** (assessments UI + public take page;
  proctoring CAPTURE LOOP still deferred — presign wiring only). Remaining: F6 CRM board +
  vendor screens → F7 notification center + founder trend charts. Hosting still deferred
  (C1/D.6).
- **NEW — admin staff-roster endpoint:** /admin/employees UI stays ComingSoon until a small
  backend endpoint lists staff users+roles (no such surface exists; deliberate guard stop).
- **Hosting still deferred (C1/D.6):** the frontend is local-only; "done" = built + verified
  against the local/dev API.
- **F2+ slice order (proposed):** F2 recruiter pipeline interactions + candidate portal tabs
  (jobs/applications) → F3 assessments UI (issue/track/waive + the public take page) →
  F4 placements/invoices/commissions screens → F5 CRM board + vendor screens →
  F6 notification center + founder trend charts + admin employees/SLA board.

### D10. B.13 vendor depth — deferrals + a pending BUSINESS INPUT (added 2026-07-04)
- **Pending business input:** the **vendor GLOBAL default commission %**
  (`VENDOR_COMMISSION_DEFAULT_PERCENT`) ships unset — accrual without an override/client-rate/
  valid-contract is refused (409) rather than guessing a commercial term (same class as the
  GST rates / C.2 fee decision). When vendors are onboarded at scale, the founder owes a
  number; setting the env activates the fourth resolution level with zero code change.
- **Deferred:** (a) payout integration / actual money movement = Part D (mark-paid is
  lifecycle only); (b) vendor-submission create UI = frontend workstream.
- **D3 → RESOLVED 2026-07-04:** contracts, client-dynamic commissions (resolver with
  source-level audit), performance scorecards — B.13, migration 0031.

### D9. B.11 founder dashboard — scale-up deferrals (added 2026-07-04)
- **What:** (a) **nightly materialized read-model tables** — v1 aggregates on-read + Redis
  cache (fine at dev volume); when data volume makes on-read slow, add materialized tables
  behind the same `app/reporting.py` functions (the interface is the seam). (b) ACADEMY/
  CONSULTING by-bu columns are present-but-zero and fill in automatically when those verticals
  land (D1). (c) predictive/AI metrics (forecasts, health scores) = the V2 backlog — the
  dashboard stays descriptive until then.
- **Trigger:** (a) volume/latency; (b) B.17/B.18; (c) V2 gates.

### D8. B.10 notifications — enqueue wired; real DELIVERY = Part D (added 2026-07-04)
- **What:** the notification pipeline is LIVE (templates, enqueue, idempotency ledger,
  ConsoleChannel dev sink, send sweep in the commercial-jobs runner). The three former stubs —
  **B.7 assessment result, B.8 interview reminder, B.9 dunning** — now ENQUEUE; actual
  delivery to real recipients needs Part D: register `EmailChannel` (SES — includes the .ics
  attach and the METHOD:CANCEL cancellation path) / `SmsChannel` / `WhatsAppChannel` in
  `notify.CHANNEL_REGISTRY` and clear `NOTIFY_CHANNEL_OVERRIDE`. Parked pending rows are
  picked up automatically — zero call-site changes.
- **Also:** dunning cadence (today: one notice per invoice, `invoice_dunning:<id>`) is a
  Part-D policy decision; template copy is PROVISIONAL operational text — refine before real
  sends (legal/consent notices remain STOP-3/A1).
- **Trigger:** Part D (D.3/D.5) — SES production access + provider onboarding.

### D7. B.9 commercial layer — deferred wiring (added 2026-07-04)
- **What:** (a) the guarantee/dunning sweeps run via `backend/scripts/run_commercial_jobs.py`
  as a ONE-OFF ECS task (repo pattern) — the **EventBridge Scheduler → ECS RunTask daily rule
  is not yet in Terraform** (free, small addition). Correctness does NOT depend on it: the
  guarantee state is derivable from dates on every read and the sweep self-heals.
  (b) **Dunning EMAIL delivery** — detection is live (`GET /api/invoices/overdue`); the send
  is stubbed until B.10 notifications + SES (Part D). (c) Invoice **numbering format,
  HSN/SAC, GST/TDS rates** remain C.3/B5 inputs — PDF marks numbering PROVISIONAL and taxes
  "pending" until then.
- **Trigger:** (a) next Terraform session; (b) B.10; (c) CA input (C.3).
- **RESOLVED input for the record — C.2 placement fee (2026-07-04):** 15% flat default,
  **annual-CTC base**, client-level override (`clients.fee_percent`), per-invoice override on
  top, before tax. Implemented + test-locked in B.9.

### D6. B.7 aptitude engine — deferred pieces (added 2026-07-04)
- **What:** the backend engine is live (issue/take/grade/waiver, dev-deployed). Deferred:
  (a) the **take-test FRONTEND** — browser lockdown/fullscreen, face-api.js, the snapshot
  capture LOOP (B.7 provides the upload presign + proctor_flags storage only);
  (b) the **result email** ("result within 30 min") — needs B.10 notifications + SES (Part D);
  result currently surfaces in-app/on the dashboard only;
  (c) **real question-bank CONTENT** — the seeded bank is 12 clearly-marked SAMPLE questions;
  real banks are a Part-C input from the user.
- **Note:** `FEATURE_ASSESSMENT_WAIVER` is the per-tenant demo/policy toggle for the admin
  assessment waiver — **OFF by default** (waiver endpoints 404); flip per environment/tenant
  deliberately. A waived pass always shows `waived=true` + `score=NULL`.
- **Trigger:** (a) the take-test frontend slice; (b) B.10/SES; (c) whenever question content arrives.

### D5. Frontend kanban uses the pre-B.5 stage vocabulary (added 2026-07-04)
- **What:** B.5 (migration `0024`) replaced the 9-stage vocabulary with the full 21-stage
  Part-5 set and routed all stage changes through `pipeline.transition()`. The deprecated
  `PATCH /applications/{id}/stage` shim still works (through the guard) but accepts NEW
  stage names only — the local-only frontend kanban (`/employer/pipeline`) still sends
  `screened`/`assessed`/… and its columns render the old names, so drag-drop is functionally
  broken until the frontend adopts the new vocabulary (and ideally the new
  `POST /transition` endpoint with `expected_version` for real optimistic-lock UX).
- **Why deferred:** frontend is out of B.5 scope and not deployed anywhere.
- **Blocks:** the local kanban demo flow only.
- **Trigger:** next frontend session (B.16 portal polish, or the first frontend-deploy slice).

### D4. Client portal — follow-ups (non-blocking)
- **What / why deferred:** (a) **client account activation** — admin currently sets an initial password on approval;
  the real flow is an **invite link / set-password email** (no email infra yet). **Also applies to HR-invited
  teammates** (Task 7): `POST /api/client/team` likewise sets an initial password inline — same invite-link/SES gap.
  (b) **Legacy `/employer/*` staff
  screens** (the recruiter client-management tools built earlier) are no longer linked from the `client` nav (which now
  = the external client portal); give internal staff their own nav entry / role mapping. (c) Client **consent notices**
  reuse the stubbed `[LEGAL COPY TBD]` (tracked in A1) — no real-client onboarding until real wording + hCaptcha keys (A2).
  (d) **Client-role UI polish** (Task 7): the Offers + Team nav items render for BOTH client roles; a hiring manager
  who opens Team sees an "HR access only" notice and the API enforces 403, but hiding the nav item for managers (needs
  the role at the server-rendered nav layer, currently role-agnostic) is a nice-to-have.
- **Blocks:** real client onboarding (pairs with A1 legal copy + A2 hCaptcha keys); polished staff/manager UX.
- **Trigger:** when adding email/invite infra (covers HR teammate invites too); at real-user launch prep (with A1/A2);
  a staff-nav cleanup pass.

### D3. Vendor management — depth beyond the core (follow-up)
- **What:** core built — `staffing.vendors` + `staffing.vendor_submissions` (CRUD + attribution + status).
  NOT built: `vendor_contracts`, `vendor_commissions` (commission calc/payout against placements),
  `vendor_performance`. Also: vendor-submission *creation* UI (backend endpoint exists + tested;
  the screen currently lists/updates, creation is via API).
- **Why deferred:** Part 5 calls vendor depth V2; core is enough for attribution now.
- **Blocks:** commission payouts + vendor scorecards.
- **Trigger:** when vendor commissions/performance are prioritized.

### D2. Rate-limiting the public registration endpoint (hardening)
- **What:** `POST /api/register/candidate` is public; no rate limit yet (captcha + dedup
  unique are the current guards).
- **Why deferred:** recommended hardening, not built.
- **Blocks:** nothing yet; reduces abuse surface.
- **Trigger:** before/with opening real signups (pair with A1/A2); implement via Redis.

---

## E. Ops / account / email

### E1. DKIM for `spstechnosoft.com`
- **What:** DKIM DNS records still absent (GoDaddy). (BUILD-LOG also notes Microsoft 365
  DKIM CNAMEs — same gap, the email setup.)
- **Why deferred:** DNS/email setup follow-up.
- **Blocks:** email deliverability / domain auth (SPF/DKIM/DMARC alignment).
- **Trigger:** email-setup pass; add the DKIM records in GoDaddy.

### E2. Branch protection (Option B)
- **What:** GitHub branch protection deferred.
- **Why deferred:** until dev is validated end-to-end with the frontend UI.
- **Blocks:** enforced PR review/checks on `develop`/`main`.
- **Trigger:** once dev is validated end-to-end with frontend UI.

### E3. GST tax number on the AWS account
- **What:** add the GST tax number in AWS account tax settings.
- **Why deferred:** billing/account admin.
- **Blocks:** GST-compliant AWS invoicing.
- **Trigger:** account-admin pass.

### E4. CI deploy OIDC retry-storm (transient failures burn ~16 min)
- **What:** the `deploy` job's `Configure AWS credentials (OIDC)` step can intermittently fail
  with `Could not assume role with OIDC: Token expired` and then keep retrying
  `AssumeRoleWithWebIdentity` **past the 15-min OIDC token TTL** — observed ~16 min of doomed
  retries before failing the run (seen 2026-06-28 on the export-PII deploy; the next run with no
  changes succeeded → transient infra, not config).
- **Why deferred:** transient/low-frequency; non-blocking.
- **Blocks:** nothing functional — but wastes a CI run and currently needs a **version-bump
  workaround** to retrigger (see below).
- **Fix options to record:** (a) **bound/fast-fail** the `configure-aws-credentials` retries
  (e.g. `retry-max-attempts`/lower timeout) so a run doesn't retry past the token TTL — fail fast
  instead; (b) grant **repo-admin re-run rights** so a transient failure can be re-run with
  `gh run rerun --failed` instead of pushing an empty/version-bump commit (empty commits don't
  trip the `paths` filter, so a real no-op change is currently required to retrigger).
- **Trigger:** next time CI/`.github/workflows/deploy-dev.yml` is touched.

---

## Minor / future options (non-blocking)
- `email_bidx` blind index for email (email currently CITEXT) — add if email must leave plaintext.
- `aadhaar_enc`/`aadhaar_bidx` column — add when an Aadhaar-collection feature arrives (encryption layer already supports it).

---

## Resolved (kept for history)
- **C5: S3 resume object lifecycle (upload + extraction + erasure delete)** — RESOLVED 2026-07-04
  (master plan **B.1**, migration `0020`): resume upload now exists — staff-gated
  presign→PUT→confirm flow (`app/routers/resumes.py`, `app/storage.py`) writing
  `resume_s3_key`/`resume_uploaded_at` + server-side text extraction (`app/resume_parse.py`,
  pdfminer.six/python-docx) into `resume_text`; presigned GET for download. Erasure now
  **deletes the S3 object** (`storage.delete_object`; task role already had `s3:DeleteObject`)
  and nulls `resume_s3_key`/`resume_text`/`resume_uploaded_at` in the anonymize scrub
  (extracted text is PII). The `settings.storage_bucket`/`S3_BUCKET` env mismatch is fixed
  (AliasChoices — the field now reads the env ECS injects). Verified: 118 tests local (moto)
  + one-off real-S3 probe on dev (`backend/scripts/verify_resume_s3.py`). **Remaining split
  out:** the timeline `ResumeUpload` event is deferred to **B.2** (TODO hook in code).
- **DPDP export now includes the principal's own decrypted PAN/phone** — RESOLVED 2026-06-28:
  `_export_bundle` undefers + decrypts `*_enc` for the principal's OWN candidates (matched by
  tenant+email); scope-tested (A's export has A's PII, zero of B's). Export is the privileged,
  audited decryption path (writes an `audit_logs` `dpdp.export` entry with `pii_disclosed`,
  who/when) and is NOT idempotency-cached (decrypted PII must not be written to Redis). Admin
  views stay masked.
- **audit_logs / consents append-only enforcement** — RESOLVED 2026-06-28: the backend now
  connects as a least-privilege role **`sps_app`** (Secrets Manager `sps-shared-dev-app-db`,
  wired in `appdb.tf`) with full DML on business tables but only SELECT/INSERT on
  `shared.audit_logs` + `shared.consents` → append-only is **DB-enforced**. Migrate task
  stays on master (DDL). Verified on dev RDS: app works as `sps_app` (registration 200,
  /readyz ok) AND UPDATE/DELETE denied on both ledgers. Role provisioned via the idempotent
  one-off bootstrap (`backend/scripts/bootstrap_app_role.py`).
- **PII encryption (was a HARD BLOCKER)** — RESOLVED 2026-06-28: PAN/phone KMS-encrypted
  (`alias/sps-pii-dev`) + HMAC blind index; expand/contract migrations 0006–0008 live;
  verified on dev RDS+KMS. Real-PII candidate write paths now permitted.
- **next-intl moderate advisories** — RESOLVED (F5): bumped to 4.13.0.
- **HTTPS/ACM on the ALB** — RESOLVED: `dev-api.spstechnosoft.com` serves HTTPS (ACM cert live).
