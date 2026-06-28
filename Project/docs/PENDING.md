# Outstanding / Deferred — DO NOT SKIP

**This file is the single source of truth for everything deferred in the SPS build.**
Claude Code must read it at the start of any session before assuming work is "done,"
and must not silently skip any item here. When an item is resolved, move it to
**Resolved** at the bottom with the date. When new deferrals happen, add them here
(with: what / why deferred / what it blocks / trigger to pick up).

Last refreshed: 2026-06-28.

---

## A. Blocks taking REAL users (launch-critical — pair these before any real signup/demo)

### A1. DPDP / legal copy — all `[LEGAL COPY TBD]` (STOP-3)
- **What:** Real wording for: candidate-registration consent text, the DPDP consent
  notices (`data_processing` / `marketing` / `cookies` in `app/routers/privacy.py` →
  `POLICY_TEXT`), the privacy policy, and the terms of service. All are placeholders.
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

### C5. S3 resume object lifecycle (upload + erasure deletion) — surfaced by the erasure data-map
- **What:** `staffing.candidates.resume_s3_key` points at a resume file in the storage bucket
  (`sps-shared-dev-storage-<acct>`). Two gaps: (1) **no resume-upload code exists yet** (the column
  has no writer); (2) **erasure must delete the S3 object**, not just the DB row — S3 is outside the
  DB cascade. Minor note: `settings.storage_bucket` default (`sps-technosoft-dev-storage`) differs
  from the real bucket; deployed uses the `S3_BUCKET` env (correct), so this only matters if the
  default is ever relied on.
- **Why deferred:** resume upload not built; erasure deletion gated on the B1 design decisions.
- **Blocks:** complete erasure (resume PII would survive a DB-only erase); resume feature itself.
- **Trigger:** when building resume upload (add S3 PII to the data map) AND when building erasure
  execution (delete the S3 object as part of the cascade).

---

## D. Product scope not yet built

### D1. Other verticals — Academy (Training/Internship) & Consulting (IT Services) portals
- **What:** only the Staffing vertical is built. Academy + Consulting portals are not.
- **Why deferred:** sequencing — Staffing first.
- **Blocks:** those product lines.
- **Trigger:** when the standing sequence reaches them.

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
