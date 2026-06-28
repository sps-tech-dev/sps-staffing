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

### A2. hCaptcha real keys (STOP-4)
- **What:** Mechanism is wired (`app/captcha.py`: real `siteverify` when `HCAPTCHA_SECRET`
  set; frontend `/register` uses hCaptcha's TEST sitekey otherwise). No real account/keys.
- **Why deferred:** needs an hCaptcha account (site key + secret) — user's STOP-4 decision.
- **Blocks:** real candidate signups (bot protection is in test mode = effectively open).
- **Trigger:** create hCaptcha account → add a Secrets Manager scaffold (like `pii.tf`) for
  the secret, set `HCAPTCHA_SITEKEY` (public env) + `HCAPTCHA_SECRET` (secret, **set
  out-of-band, never in git**) on the backend task def + IAM GetSecretValue. Pair with A1.

### A3. Deployed-dev real login (STOP-4)
- **What:** `dev-api` mints no tokens (founder is `invited`; JWT secrets are unexercised
  defaults). Local loop does real logins meanwhile.
- **Why deferred:** needs JWT secret → Secrets Manager + ECS task-def `secrets` wiring +
  execution-role IAM grant + `COOKIE_SECURE=true` + an activated dev user (STOP-4).
- **Blocks:** clickable login on `dev-api`; any UAT/stakeholder demo on dev.
- **Trigger:** before any UAT/stakeholder demo on dev-api.

---

## B. DPDP / compliance follow-ups

### B1. DPDP erasure execution engine (sensitive — design with user first)
- **What:** `POST /api/privacy/erase` records a `pending` `dpdp_requests` row only; there is
  NO actual deletion/redaction cascade.
- **Why deferred:** needs a deliberately-designed, reviewed cascade + a decision on what
  DPDP requires erased vs. what is legally retained. Irreversible.
- **Blocks:** fulfilling real erasure requests.
- **Trigger:** design the cascade WITH the user before building (do not auto-implement).

### B2. DPDP export completion (include the principal's own PII)
- **What:** `app/routers/privacy.py` `_export_bundle` omits `phone`/`pan`. Now that
  decryption exists, a data-access export should include the principal's own decrypted
  phone/pan.
- **Why deferred:** was omitted while PII was unencrypted; now unblocked.
- **Blocks:** a complete DPDP right-to-access export.
- **Trigger:** pick up any time (low risk) — decrypt + include in the export bundle.

### B3. audit_logs / consents append-only enforcement — ✅ RESOLVED (see Resolved section)

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

---

## Minor / future options (non-blocking)
- `email_bidx` blind index for email (email currently CITEXT) — add if email must leave plaintext.
- `aadhaar_enc`/`aadhaar_bidx` column — add when an Aadhaar-collection feature arrives (encryption layer already supports it).

---

## Resolved (kept for history)
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
