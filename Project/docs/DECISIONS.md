# SPS Staffing — Architectural Decisions

Short, dated records of key decisions: **what** was decided, **why**, and **what
would change it**. Newest at the bottom.

> 📌 **Outstanding/deferred work lives in [`docs/PENDING.md`](PENDING.md)** — the single
> source of truth for everything not yet done. Read it each session; do not skip its items.

---

### 2026-06-26 — GoDaddy DNS over Route 53
- **Decision:** Host `spstechnosoft.com` DNS at GoDaddy, not AWS Route 53.
- **Why:** The Route 53 zone lived in the *old* AWS account; moving DNS to GoDaddy decouples the domain from that account and lets us decommission it cleanly.
- **Would change if:** We consolidate everything into the new AWS account and want Route 53 features (alias records, health checks, latency routing) — then migrate the zone in.

### 2026-06-26 — IAM users over IAM Identity Center (SSO)
- **Decision:** Use plain IAM users (`priyanka-admin`, `priyanka-cli-admin`) rather than IAM Identity Center.
- **Why:** Simplicity for a 2-person team; Identity Center adds setup/operational overhead not justified at this size.
- **Would change if:** The team grows, we need federated/temporary credentials, or multiple AWS accounts — revisit Identity Center then.

### 2026-06-26 — Single NAT gateway (dev)
- **Decision:** One NAT gateway shared by both private tiers in dev.
- **Why:** Cost-saver (~$32/mo vs ~$64+ for one-per-AZ); a single AZ NAT outage is acceptable in dev.
- **Would change if:** Production — use one NAT gateway per AZ for high availability.

### 2026-06-26 — $50/mo budget ceiling
- **Decision:** Cap dev budget alerts at $50/mo.
- **Why:** Matches the real expected dev footprint (single NAT + small RDS/Redis/ECS); tight enough to catch runaway spend early.
- **Would change if:** Workload grows or we add prod — raise ceiling and split budgets per environment.

### 2026-06-26 — Three-tier subnet design
- **Decision:** Public / private-app / private-data subnet tiers across 2 AZs.
- **Why:** Network isolation — only the ALB is internet-facing (public); app (ECS) and data (RDS/Redis) tiers have no inbound internet path, reducing blast radius.
- **Would change if:** Requirements simplify drastically (unlikely) or we need additional tiers (e.g., a dedicated egress/management tier).

### 2026-06-26 — SG-to-SG references over CIDR
- **Decision:** Security group rules reference other security groups, not IP CIDR ranges (except the ALB's public ingress).
- **Why:** Least privilege that follows workloads — membership-based rules stay correct as instance IPs change; no brittle CIDR maintenance.
- **Would change if:** We need to allow specific external IPs (e.g., office/VPN) — those become explicit CIDR rules.

### 2026-06-26 — Tenant-isolation strategy deferred to app data-model phase
- **Decision:** Terraform provisions only the RDS instance with the default `public` schema and database `sps_staffing_dev`. It does **not** create schemas, roles, or tenant structures. The choice between shared-schema (tenant_id column), schema-per-tenant, and database-per-tenant is deferred.
- **Why:** Tenant isolation is an application data-model concern owned by the app migration layer (FastAPI / SQLAlchemy / Alembic), not infrastructure. Encoding it in Terraform would couple schema design to infra changes and fight the ORM/migration tooling.
- **Would change if:** We pick database-per-tenant or need infra-managed per-tenant resources (separate DBs/instances) — then provisioning re-enters Terraform's scope.

### 2026-06-26 — Redis (ElastiCache) cost lever: destroy, not stop
- **Decision:** Run a single-node `cache.t4g.micro` Redis (~$11/mo). The dev cost lever for idle periods is to `terraform destroy` just the Redis resources (subnet group + replication group) and `terraform apply` to recreate them — **not** a stop/start.
- **Why:** Unlike RDS, **ElastiCache has no stop/start API** — a running node bills continuously and the only ways to cut cost are node size (already the smallest) or removal. Redis here holds only cache/broker data (sessions, rate limits, queues), which is ephemeral and safe to lose, so destroy-and-recreate carries no data risk.
- **Would change if:** Redis ever holds durable state, or prod — then add replicas (`num_cache_clusters` ≥ 2, `automatic_failover_enabled`, `multi_az_enabled`), enable `transit_encryption_enabled`, and treat it as non-disposable.

### 2026-06-26 — Canonical naming convention (CANONICAL — supersedes `sps-staffing-dev-*` for shared infra)
- **Decision:** Adopt a single naming + tagging convention for all AWS resources:
  - **Names are lowercase-hyphen only** (no underscores, no caps) — required by S3/RDS/ElastiCache/etc.
  - **Shared platform layer** (VPC, IGW, subnets, NAT, route tables, security groups, RDS, Redis — used by all three verticals) is prefixed **`sps-shared-dev-*`** and tagged `Vertical = shared`.
  - **Per-vertical resources** (future ECS services, ECR repos, vertical S3 buckets) are prefixed **`sps-staffing-dev-*`**, **`sps-edtech-dev-*`**, **`sps-itservice-dev-*`** and tagged `Vertical = staffing | edtech | itservice`.
  - **Common tags on everything:** `Project = sps`, `Environment = dev`, `Vertical = <…>`, `ManagedBy = terraform`. (`Project`/`Environment`/`ManagedBy` come from provider `default_tags`; `Vertical` is set per-resource.)
- **Why:** The earlier `sps-staffing-dev-*` prefix mislabelled shared infrastructure as if it belonged to the staffing vertical. The platform serves three verticals on one shared spine; the prefix must reflect ownership so cost allocation, incident response, and per-vertical resources stay unambiguous.
- **Would change if:** We split verticals into separate AWS accounts (then account boundary replaces the `shared` prefix) or add environments (the `dev` token extends to `staging`/`prod`).

### 2026-06-26 — One shared database, schema-per-vertical (CANONICAL)
- **Decision:** A single shared RDS instance **`sps-shared-dev-rds`** hosts one database **`sps_platform_dev`** containing four schemas — `shared` (auth, users, audit, notifications — the shared spine), `staffing`, `academy`, `consulting`. **Schemas are created by the application's Alembic migrations, not Terraform.**
  - **Per-tenant PRODUCT access** (e.g. a tenant who bought Staffing only) is enforced at the **application entitlement layer** via a `shared.tenant_subscriptions` table — **not** by database separation. The DB topology is invisible to tenants; they only ever reach the app.
  - **Per-tenant DATA isolation** is by `tenant_id` columns (+ `business_unit_id` for vertical), enforced in the base repository.
- **Why:** Separate-DB-per-vertical was **considered and rejected** — Postgres has TB-scale headroom, so recruitment data size is not a real limit; separate DBs would break cross-vertical joins (e.g. the Academy→Staffing candidate flow) and complicate the shared spine. Large recruitment tables, if they ever need it, are handled by **partitioning within the `staffing` schema**, not by separating databases.
- **Would change if:** A vertical needs hard physical isolation (compliance/data-residency) or independent scaling — then promote that vertical to its own database/instance (re-entering Terraform's scope), accepting the loss of cross-vertical joins. [[tenant-isolation-deferred]]

### 2026-06-26 — Canonical app location: `~/Staffing and Recruitment/backend/`
- **Decision:** The deployable backend lives at **`~/Staffing and Recruitment/backend/`** — a sibling of `Project/` (Terraform infra) and separate from `Context/spstechnosoft-platform/backend/` (read-only reference). Images are built and pushed from this folder.
- **Why:** Keeps three concerns cleanly separated — infra (`Project/`), app source (`backend/`), and the original spec/reference bundle (`Context/`). The Context copy must stay pristine as the architecture reference; mutating it for builds would blur that line.
- **Would change if:** The app graduates to its own git repo / the `spstechnosoft-platform` monorepo becomes the working tree — then point the build context there and retire the sibling copy.

### 2026-06-26 — Backend image is ARM64 (Graviton) → Fargate must run ARM64
- **Decision:** The backend image is built `arm64/linux` (the dev machine is Apple Silicon). The ECS Fargate service will set `runtime_platform { cpu_architecture = "ARM64", operating_system_family = "LINUX" }` to match.
- **Why:** Consistent with the platform's Graviton/`t4g` cost choices, and avoids a cross-build. Default Fargate is X86_64 and would fail to launch an arm64 image.
- **Would change if:** CI builds images on x86 runners, or we need x86-only base images — then build multi-arch (`--platform linux/amd64,linux/arm64`) or switch the task to X86_64.

### 2026-06-26 — S3 storage: private bucket, pre-signed URLs, key prefix mirrors DB partitioning
- **Decision:** One shared bucket `sps-shared-dev-storage-412058343855` (account-ID suffix for global uniqueness) in `ap-south-1`, tagged `Vertical = shared`.
  - **Private only:** all four public-access-block flags on; **no** bucket policy granting anonymous/public access. Stores personal data (resumes, candidate docs) → DPDP requires no public exposure.
  - **Access model:** exclusively via the app's ECS **task role** (scoped to this bucket only — `Get/Put/DeleteObject` on `…/*`, `ListBucket` on the bucket ARN) plus **pre-signed URLs** issued by the app for client up/download. Browsers never hit the bucket directly with credentials.
  - **Key-prefix convention** (mirrors the DB two-axis partitioning): `tenant=<tenant_id>/business_unit=<vertical>/<entity>/<file>` — keeps object ownership aligned with `tenant_id` + `business_unit_id` and makes per-tenant export/erase (DPDP) and lifecycle scoping straightforward.
  - Encrypted at rest (SSE-S3/AES256 for dev), versioned (accidental-delete recovery), incomplete multipart uploads aborted after 7 days. **Residency:** `ap-south-1` (DPDP India).
- **Why:** Personal-data storage must be private and least-privilege; pre-signed URLs avoid distributing AWS credentials to clients; mirroring the DB partition keys keeps storage and data tenancy consistent.
- **Would change if:** Prod / stricter compliance — SSE-KMS with a CMK (per-key audit/rotation), cross-region replication for DR, S3 access logging, and storage-class transitions + DPDP retention expiry. Per-tenant buckets only at the DB-per-tenant isolation phase. [[one-shared-database-schema-per-vertical]]

### 2026-06-26 — Data-model conflict resolutions A–E (shared spine, migration 0002)
Discovery surfaced internal inconsistencies in the architecture spec. Resolved as follows (the running app + Part 12 + Part 32 win where the spec conflicts with itself):
- **A — `business_unit_id` type:** On **business/vertical** tables it is **TEXT + CHECK** (`STAFFING|ACADEMY|CONSULTING`), NOT a PG enum and NOT uuid — matches `app/context.py` (path→string) and Part 12/Part 32 ("enums as text + CHECK"). `business_units` stays a **uuid registry** table whose `code` holds that same TEXT value; `memberships.business_unit_id` is the uuid FK to that registry (identity link, not the partitioning axis).
- **B — Audit tables are mixin exceptions:** `audit_logs` uses **bigserial PK**, no `updated_at`/`deleted_at`, append-only; the `TwoAxisMixin` is NOT applied. `audit_logs.business_unit_id` is TEXT (per A). Append-only enforcement via DB `REVOKE UPDATE/DELETE` is **deferred** until a dedicated least-privilege app DB role exists (app currently connects as the master user). `candidate_timeline` is NOT in the spine — it belongs to the `staffing` schema (later migration).
- **C — Entitlements per spec:** `plans` + `tenant_subscriptions` (1:1 with tenant) + jsonb `limits`/`features`. Vertical access is encoded in jsonb feature flags, NOT per-(tenant,BU) subscription rows.
- **D — Subdomain slug:** `tenants` gets **`slug text UNIQUE NOT NULL`** (the subdomain, e.g. `ampf`), **distinct** from `code` (the formal ID, e.g. `SPS001`).
- **E — Naming:** plural **`tenant_subscriptions`** (deviates from the spec's singular `tenant_subscription`, to match the plural table convention).
- **Base-model pattern:** `TimestampMixin` (created_at/updated_at) + `TwoAxisMixin` (uuid PK, tenant_id, business_unit_id TEXT+CHECK, timestamps, deleted_at) live in `app/mixins.py` for **future vertical tables**. The identity spine does NOT use `TwoAxisMixin` (tenants has no tenant_id; users/business_units have no business_unit_id).
- **Would change if:** A dedicated app DB role is introduced (then enforce audit append-only via grants); or per-vertical entitlement rows are needed (then extend beyond the plans/subscription model).

### 2026-06-26 — No credentials in the repo; founder password set out-of-band
- **Decision:** Seed migration `0003` creates the founder user (`sandeep@spstechnosoft.com`) **password-less**: `status = 'invited'` and a **sentinel `password_hash = '!'`** (not a real argon2 hash, not a hash of any known password — argon2 `verify()` rejects it, so the account cannot log in). The real password is set **out-of-band** via `scripts/set-founder-password.sh`, never committed.
- **The helper** keeps plaintext **only in the local terminal**: it prompts hidden (twice), enforces a strength floor (≥12 chars, rejects weak/predictable patterns), hashes locally with **argon2** inside the app image (same scheme the app verifies with — plaintext piped via stdin, never to disk/logs), then runs a one-off ECS task in the VPC that `UPDATE`s `shared.users` (status→`active`) receiving only the non-reversible **hash** via an env override (parameterized query; hash never printed). RDS creds come from Secrets Manager, same path as the app/migration.
- **Why:** Secrets (even hashes of real passwords) must never enter source control; a password-less seed with out-of-band activation keeps the repo credential-free while still bootstrapping the owner account. argon2 matches the app's planned verification.
- **Would change if:** ECS Exec is enabled (could run the hash+update fully inside a container with no hash crossing the ECS API), or a proper invite/password-reset email flow replaces the manual helper.

### 2026-06-26 — Branching model: develop → dev, main → prod
- **Decision:** `develop` is the integration branch and **deploys to the dev AWS environment** (the one already built). `main` is the stable branch, **reserved for prod later** (no deploy target yet). The GitHub Actions OIDC **dev-deploy role trust is scoped to the `develop` branch only** (`sub = repo:sps-tech-dev/sps-staffing:ref:refs/heads/develop`).
- **Why:** Keeps integration work flowing to dev continuously while `main` stays a clean, protected line for the eventual prod cutover; scoping the deploy role to one branch of one repo means only `develop` pushes can assume AWS deploy creds.
- **Would change if:** Prod is stood up — add a `main`-scoped (or tag/environment-scoped, with a required-reviewers GitHub Environment) prod-deploy role; possibly add `staging`. Default branch on GitHub is being set to `develop` (manual web-UI step).

### 2026-06-27 — CI/CD pipeline + migration policy (dev auto, UAT/prod gated)
- **Decision:** `.github/workflows/deploy-dev.yml` runs on push to `develop` (+ manual `workflow_dispatch`): OIDC auth → build ARM64 image → push to ECR → register new backend+migrate task-def revisions (fetch-and-modify the LIVE task defs, swap image only — zero drift) → **run migrations FIRST (expand/contract)** → then update service + `wait services-stable` → health-check `/healthz` + `/readyz`. Migrate-before-deploy guarantees new code never starts against a not-yet-applied schema; a failed migration aborts before the service is touched.
  - **Migrations: dev = AUTOMATIC (Option 1)** — always `alembic upgrade head` (idempotent), no gate.
  - **UAT/prod = GATED (Option 2)** — migrations run as a separate job targeting a GitHub `environment:` with **required reviewers**, triggered from main/tags. **Stubbed as a commented extension point in the workflow, NOT implemented** (those environments don't exist yet).
  - Concurrency: one deploy per branch, **queue (no cancel)** so an in-flight ECS rollout/migration is never interrupted.
  - Keyless: assumes `sps-shared-dev-gha-deploy` (no stored AWS keys). The migrate run-task reuses the **service's own network config** (private-app subnets + ecs SG) so the role needs no `ec2:Describe*`.
- **Why:** Dev iterates fast (auto-migrate is safe given idempotent, additive migrations + DB-independent boot); prod must never auto-migrate without human approval.
- **Would change if:** prod/uat stand up (implement the gated job + environments); or migrations become non-idempotent/destructive (add expand-contract gating even in dev).

### 2026-06-27 — Frontend: adopt the web-starter as `frontend/` (monorepo); npm; security baseline
- **Decision:** The frontend is the `spstechnosoft-web-starter` (Next 15 · React 19 · TS · Tailwind v4 · TanStack Query), landed as **`frontend/`** in this monorepo alongside `Project/` (infra) + `backend/` (app) — one repo, one pipeline. The separate `spstechnosoft-platform/` skeleton is **rejected** (assumes a different infra/backend layout than our proven `Project/`+`backend/`).
- **Package manager: npm** (the starter ships `package-lock.json`; pnpm not installed on the build machine). `package-lock.json` committed for reproducibility.
- **Security baseline:** Next pinned to **15.5.19** (patched) + React **19.2.7** — clears the critical/high Next CVEs (middleware/auth-bypass, dev-server origin, SSRF, RCE flight-protocol). Flat ESLint config added; `next lint` is deprecated (migrate to `eslint .` CLI before any Next 16 move).
- **Deferred security item (TRACKED, not optional):** `next-intl` has a moderate open-redirect + prototype-pollution advisory; **must bump to `next-intl@4+` when the i18n slice (F5) is built** — do not ship i18n on the vulnerable version.
- **Would change if:** we adopt pnpm (regenerate lockfile); or split the monorepo when team size warrants.

### 2026-06-27 — Tenant isolation: JWT `tenant_id` is the authoritative boundary; Host↔session cross-check DEFERRED (TRACKED)
- **Decision:** The backend scopes **every business query by the `tenant_id` from the verified JWT** (a signed claim the user cannot forge) — this **is** the isolation boundary. `business_unit_id` comes from the URL path, validated against the user's memberships. The **Host↔session cross-check (subdomain tenant vs JWT tenant → 403) is DEFERRED** — it is defense-in-depth that only has anything to compare once real tenant subdomains exist (multiple tenants on `*.spstechnosoft.com` behind CloudFront). Today there is one tenant (SPS001) and no subdomain routing, so localhost/dev-api both resolve to the owner tenant.
- **Why:** Matches the tenancy spec ("backend re-derives from a signed context, never trusts a raw header blindly; the JWT carries `tenant_id`"). Deferring the Host check is **not** weakening isolation — the boundary (JWT-authoritative scoping) is built now; the second layer is added when its precondition (wildcard subdomain routing) exists. A cross-tenant-leakage test (tenant A context cannot read tenant B) proves the boundary.
- **REVISIT TRIGGER:** when building **wildcard subdomain routing + CloudFront** (the F5/edge work), wire the Host↔JWT `tenant_id` cross-check at the edge (and a backend trusted-forwarded-host check) → 403 on mismatch.
- **Dev topology:** fully-local loop — backend in docker-compose (local Postgres+Redis seeded with SPS001) + Next proxy (`/api/* → API_URL`), same-origin httpOnly cookies on `localhost`. No cross-site CORS. A deployed same-origin frontend (CloudFront+ACM+domain) is future paid infra (STOP-4), not needed for auth.
- **Cookies:** `access_token` + `refresh_token`, **httpOnly**, **SameSite=Lax**, **host-only (no Domain)**, **Secure=false in dev / true in prod** (env-driven). httpOnly is non-negotiable (XSS token-theft prevention).

### 2026-06-27 — Forms UX convention: native form semantics (Tab / Enter) + shared validation
- **Decision (applies to every form, all slices):** forms are real `<form>` elements with a `type="submit"` button, so **Enter submits** and **Tab moves to the next field** natively (inputs in logical DOM order); the **first field is `autoFocus`**ed. Multi-step forms (e.g. candidate/client registration) advance the step on Enter and focus the first field of each new step. Buttons that are not submit use `type="button"`.
- **Validation:** every form composes the shared validators — frontend `lib/validation.ts` (zod: email, phone [10-digit IN], PAN, name, password, pincode, url, experience) for instant UX, and the backend **re-validates** with `app/validation.py` (authoritative) returning the Part 31 error envelope (422). Client validation is never trusted.
- **Why:** consistent, accessible keyboard behavior and one source of truth for field rules across the whole app.

### 2026-06-27 — Candidate scoping: TENANT-scoped talent pool (BU on applications)
- **Decision (STOP-2 resolution):** `candidates` are **tenant-scoped** — one record per person per tenant, NO `business_unit_id` hard-scope. Vertical ownership lives on **`applications.business_unit_id`** (the candidate↔job link). `clients`/`jobs`/`applications` remain two-axis (BU-scoped).
- **Why:** Part 19 dedup requires **one candidate per person** (email/phone/PAN) — a hard-BU candidate would force duplicate rows for a person considered across verticals, fighting dedup. The talent-pipeline + Academy→Staffing flow want a person considerable across verticals without duplication. The thing that is vertical-specific is the *application*, not the person.
- **Deviation noted:** Part 5's literal DDL has `business_unit_id` on `candidates`; we deliberately drop it there (it was the blanket two-axis pattern; the BU belongs on the application). `TenantScopedRepo.base_query` scopes candidates by `tenant_id` only (it already adds `business_unit_id` only when the model has that column).
- **Would change if:** a vertical needs its own isolated candidate pool (compliance) — then add a BU/owner column or a per-vertical table. Revisit if Academy needs `candidates` (it uses `students`).

### 2026-06-27 — PII encryption is a HARD BLOCKER before candidate registration (TRACKED)
- **Tracked blocker:** `candidates.pan` (and `phone`, future `aadhaar`) are currently **plaintext** `text` columns. Per **Part 10**, PII (PAN/Aadhaar/phone) **MUST be app-layer encrypted/tokenized BEFORE the candidate-registration slice stores real PII.** No real data exists yet (schema only), so encryption is not wired now (premature) — but it is a **hard prerequisite** for the candidate-registration slice. Do not ship candidate registration storing real PII on plaintext columns.
- **Would change if:** resolved — wire app-layer field encryption (e.g. envelope encryption via KMS or a tokenization layer) for PII columns, then registration may proceed.

### 2026-06-27 — Deployed-dev real login DEFERRED (TRACKED, STOP-4)
- **Deferral:** Real login on `dev-api` is deferred — it needs the **JWT secret in Secrets Manager + ECS task-def `secrets` wiring + execution-role IAM grant + `COOKIE_SECURE=true` + an activated dev user** (STOP-4: paid infra/IAM). The **local docker-compose loop does real logins** meanwhile (real argon2 + JWT + cookies). **Revisit before any UAT/stakeholder demo on `dev-api`.** Until then the deployed dev backend exposes the auth endpoints (failure paths verified) but mints no tokens (founder there is `invited`, secrets are unexercised defaults).

### 2026-06-27 — i18n architecture: next-intl@4, cookie-based (no locale routing), scoped to the marketing route group
- **Decision (F5):** Bumped **next-intl 3 → 4.13.0** (mandatory security bump) and wired i18n **without locale routing** — the locale is resolved from a `NEXT_LOCALE` cookie (`en` default, `hi` supported) in `i18n/request.ts`'s `getRequestConfig`. i18n is **scoped to the `(marketing)` route group** via its own `layout.tsx` + `NextIntlClientProvider`; the authenticated app (`(auth)`/`(portal)`/`(admin)`) is left untouched. The marketing wrapper carries `lang={locale}` for a11y; the root `<html lang>` stays `"en"`.
- **Why not `app/[locale]/` routing (the SSG-per-locale canonical setup):** this codebase has a **single root layout** (`app/layout.tsx` owns `<html>/<body>` + fonts + Providers) serving BOTH the public marketing routes and the authenticated app, plus an **auth middleware** gating `/admin|/employer|/employee|/candidate`. Moving everything under `[locale]` would force the authenticated app into locale-prefixed routing and require recomposing locale handling into the auth middleware — an auth-touching change the standing rules say not to make casually, for marketing copy. Cookie-based i18n keeps the blast radius inside `(marketing)`, is fully reversible, and the @4 bump (the actual security requirement) is done regardless.
- **Tradeoff (accepted, tracked):** reading the cookie makes the marketing route **dynamically rendered (`ƒ`)** instead of statically pre-rendered per locale; all app pages stay static. Locale-prefixed **SSG for marketing SEO** (`/en`, `/hi` with `hreflang`) is deferred to when SEO/marketing demands it — at which point marketing can move under `[locale]` independently of the app.
- **Security:** the @4.13.0 bump clears **both** prior next-intl advisories (open-redirect `<4.9.1`; prototype-pollution via `experimental.messages.precompile`). Remaining 2 moderate audit findings are **Next's vendored postcss** (`next/node_modules/postcss`), unfixable on the latest Next 15.5.19 without `audit fix --force` downgrading to next@9 — accepted (build-time CSS, no attacker-controlled input).
- **Tooling:** migrated `next lint` → `eslint .` (flat config; `next lint` is deprecated and removed in Next 16) ahead of any future Next 16 move.
- **Note:** This F5 is the **marketing + i18n** frontend build. The **Host↔JWT `tenant_id` edge cross-check** (also tagged "F5/edge" in the tenant-isolation decision) stays **deferred** — it requires wildcard subdomain routing + CloudFront (STOP-4 paid infra), which does not exist yet. The frontend is still not deployed anywhere.

### 2026-06-27 — Feature flags + DPDP self-service (F6)
- **Feature flags:** non-GA features are OFF by default; gated routes return **404 (not 403)** when off, so the surface is indistinguishable from a missing route (probe-proof). Flags resolve from env-driven settings (`FEATURE_AI`, default false); `app/features.py` keeps a `(name, ctx)` signature so per-tenant/per-plan flags (`business_units.features` / `plans.features` JSONB) can layer on later. `GET /api/me/features` exposes resolved flags so the client renders gated widgets only when enabled (defense-in-depth: server still 404s regardless of the client).
- **AI:** `/api/ai/*` is flag-gated and returns DETERMINISTIC STUBS (no model/provider call yet) — wiring a real model is later work. Auth + tenant scoping still apply.
- **DPDP mechanisms (Part 10):** consent is an **append-only ledger** (`shared.consents`; current state = latest per (subject, purpose)). Export returns the principal's data bundle inline + records a `dpdp_requests` row. **Erasure RECORDS a request only** (`status='pending'`) — execution is deliberately NOT performed (needs a reviewed cascade/redaction policy); F6 delivers the capture + audit mechanism, not the deletion engine.
- **STOP-3 (legal wording):** consent NOTICE COPY is stubbed `[LEGAL COPY TBD]` with a visible draft banner; `policy_version` is recorded so real, reviewed notices can be versioned in later. No legal prose invented.
- **Known gaps (tracked):** (1) the export bundle intentionally omits `phone`/`pan` until app-layer PII encryption lands — a DPDP access request should eventually include the principal's own PII; revisit with the PII-encryption work. (2) The PII-encryption HARD BLOCKER remains OPEN — the pre-existing `POST /api/candidates` can persist plaintext `phone`/`pan`; no encryption yet, no real data. (3) erasure execution + the `audit_logs`/consent INSERT-only DB role are still pending.

### 2026-06-27 — PII field encryption: envelope + blind index (Part 10)
- **Decision (STOP-2, user-approved):** candidate **PAN + phone** (Aadhaar later) are encrypted at rest with **app-layer envelope encryption** (AES-256-GCM; DEK from a dedicated **KMS CMK** `alias/sps-pii-dev` via GenerateDataKey, KMS-wrapped DEK stored inline with each ciphertext). Searchability/dedup via a **deterministic blind index** per field (`*_bidx` = HMAC-SHA256 over the normalized value, keyed by a SEPARATE Secrets Manager secret). **Email stays CITEXT** (lookup/login/dedup anchor; `email_bidx` a future option).
- **Why this shape:** randomized ciphertext gives confidentiality but isn't searchable; the HMAC blind index restores exact-match + dedup uniques without storing plaintext. The two keys are kept apart so leaking one grants neither the other's capability.
- **Transparent + safe-by-default:** `EncryptedStr` (SQLAlchemy `TypeDecorator`) encrypts-on-write / decrypts-on-read, so EVERY write path — including the pre-existing `POST /api/candidates` — is covered. The encrypted columns are **`deferred=True`**, so ordinary `select(Candidate)` (lists, SLA queue, export) never bulk-decrypts PII; decryption happens only on explicit attribute access = the **privileged, audited reveal path**. Admin lists mask via the non-sensitive `*_bidx` presence (no decrypt).
- **Dedup (Part 19):** `UNIQUE(tenant_id, phone_bidx)` + `(tenant_id, pan_bidx)`; a violation → `409 DUPLICATE_CANDIDATE`. NULL bidx (no value) is exempt by SQL NULL semantics.
- **Key mode:** `PII_KMS_KEY_ID` set → KMS mode (deployed); empty → LOCAL fixed-key mode so the local loop + tests run without AWS. Migrate task gets the same keys so the 0007 backfill encrypts in the app's mode.
- **Rollout = expand/contract over TWO deploys:** deploy 1 = `0006` (add `*_enc`/`*_bidx` cols) + `0007` (backfill + dedup uniques) + cutover code (writes/reads encrypted, stops writing plaintext); deploy 2 = `0008` contract (drop plaintext `phone`/`pan`) written only after deploy 1 is verified, so plaintext isn't dropped while pre-cutover tasks may still run.
- **Infra (STOP-4, approved):** `Project/pii.tf` — KMS CMK + alias, `sps-shared-dev-pii-index-key` secret, IAM (task role: GenerateDataKey+Decrypt on the CMK + GetSecretValue on the index secret; execution role: GetSecretValue to inject `PII_INDEX_KEY`). Apply order: `terraform apply` (creates keys + updates task defs) **before** the push, since CI fetches the live task def.

### 2026-06-28 — Public candidate registration: secure intake (Part 6 / Part 10 / Part 19)
- **Endpoint:** `POST /api/register/candidate` is **unauthenticated** (public self-service). Tenant is resolved from the **Host** (`tenant_from_host` → slug; apex/localhost → owner `SPS001`) — there is no JWT for an anonymous registrant, so the subdomain is the tenant signal (consistent with the deferred Host↔JWT cross-check: the cross-check only applies once a JWT exists). Unknown host → 404.
- **Layered gates (in order):** (1) hCaptcha bot gate; (2) DPDP consent gate — **PAN/phone are not collected without `consent_data_processing=true`** (422 otherwise); (3) tenant resolve; (4) candidate persisted with PII **encrypted** (`EncryptedStr`) + blind index, duplicate phone/PAN → **409** (Part 19); (5) consent recorded in the F6 ledger against the **candidate**.
- **Consent ledger generalized (migration 0009):** `shared.consents.subject_user_id` relaxed to nullable + new `subject_candidate_id` (UUID, **soft ref** — no cross-schema FK, since candidates live in the `staffing` vertical and `shared` must not depend on it) + CHECK `num_nonnulls(subject_user_id, subject_candidate_id)=1`. So a consent row belongs to EITHER a user (DPDP self-service) OR a candidate (registration).
- **hCaptcha (STOP-4):** mechanism wired (`app/captcha.py` → real `siteverify` when `HCAPTCHA_SECRET` set; LOCAL test mode passes a present token, missing token → 400). Frontend uses hCaptcha's official TEST sitekey when none configured. **Real keys require an hCaptcha account = STOP-4** before real signups.
- **Consent legal copy (STOP-3):** notices are the stubbed `[LEGAL COPY TBD]` from privacy.py, surfaced at the point of collection with `policy_version`. **Registration cannot take real candidates until the wording is real.**
- **Frontend:** `/register` multi-step wizard (RHF + zod `registrationSchema`, per-step `trigger()`, Enter advances/submits, autofocus per step), hCaptcha widget, consent checkboxes. Added deps `@hookform/resolvers`, `@hcaptcha/react-hcaptcha` (0 new high/critical; React 19 OK).
- **Follow-up:** rate-limiting the public endpoint (Redis) is a recommended hardening, not yet built.
