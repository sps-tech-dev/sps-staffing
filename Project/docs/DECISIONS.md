# SPS Staffing — Architectural Decisions

Short, dated records of key decisions: **what** was decided, **why**, and **what
would change it**. Newest at the bottom.

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
