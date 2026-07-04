# TASKS — Build Status & Remaining Work

Generated 2026-07-04 by diffing the Context specs (Master Architecture V2 + Technical, Frontend Build Spec, Tenancy & Routing, Pre-Build Guide) against the actual codebase (`frontend/`, `backend/`, `Project/` Terraform) and the build history (`BUILD-LOG.md`, `PENDING.md` last refreshed 2026-06-28).

---

## PART 1 — WHAT IS BUILT (verified in code + logs)

### Infrastructure / P0 — ✅ complete for dev
- AWS account 412058343855 (ap-south-1), budgets ($50/mo ceiling + alerts), IAM users, MFA.
- Terraform (all applied): VPC 3-tier, SGs, RDS Postgres 16, ElastiCache Redis, ECS Fargate + ALB + ACM HTTPS, ECR, private S3 bucket, KMS PII key + blind-index secret, app-DB least-privilege role, hCaptcha secret scaffold (empty), GitHub OIDC deploy role, run-once migrate task.
- CI/CD: `develop` → dev auto-deploy (keyless OIDC, ARM64 build, migrate-first, health-checked). Backend **live at https://dev-api.spstechnosoft.com**.

### Backend / Staffing MVP core — ✅ built, deployed to dev, 107 tests passing
- Auth (login/refresh/logout/me, argon2, httpOnly JWT cookies), two-axis tenant+BU isolation via base repo, error envelope, idempotency keys.
- Staffing core: clients, jobs, candidates (PII envelope-encrypted, KMS + blind indexes), applications with server-enforced stage state machine (409 on illegal transition).
- Full workflow CRUD: submissions, offers (CTC/RTR/joining), interviews, invoices (15% fee; GST/TDS inert), vendors + vendor-submissions.
- Client portal: `client_users` identity, self-registration → admin approval → login, client_admin vs client_manager roles, owner-scoping, team mgmt + job reassignment.
- Admin API: paginated lists, audit logs, erasure-request management, client-registration approval.
- DPDP: append-only consent ledger, audited PII export, erasure Stage 1 (disable→anonymize→retain), DB-enforced append-only tables.
- Public candidate registration (hCaptcha-gated, consent-gated, dedup 409).
- Feature flags (off → 404); AI candidate-summary endpoint (deterministic stub).
- 19 Alembic migrations applied on dev RDS.

### Frontend — ✅ built, **local only, not deployed**
- All portal screens: candidate dashboard, employer (jobs/pipeline kanban/submissions/interviews/offers/invoices/vendors), client portal (role-conditioned), employee SLA hub, admin tables + client-registration queue, `/privacy-rights`, login, candidate + client registration wizards.
- Marketing site: 8 routes (home/about/services×4/career/contact), branded, chat assistant + scroll-to-top, 37/37 pages build clean. i18n en+hi (marketing only, cookie-based).

---

## PART 2 — REMAINING TASKS (prioritized)

### 🔴 P1 — Launch blockers (nothing real can go live without these)
| # | Task | Notes |
|---|------|-------|
| 1.1 | **Finalize DPDP/legal copy** — privacy policy, ToS, consent notices (candidate + client), bump `POLICY_VERSION`, remove draft banners | All currently `[LEGAL COPY TBD]`; blocks onboarding any real user |
| 1.2 | **hCaptcha production keys** — create account, `put-secret-value`, set sitekey var, redeploy | Secret exists but empty → bot protection open |
| 1.3 | **Working login on deployed dev** — wire JWT secrets into Secrets Manager + task-def, `COOKIE_SECURE=true`, activate founder on dev RDS | dev-api mints no tokens today; blocks any stakeholder demo |
| 1.4 | **Frontend deploy target** — hosting for Next.js (CloudFront/Amplify/ECS), `dev.spstechnosoft.com` or similar, CI job (currently `frontend/**` is paths-ignored) | Entire UI is localhost-only |
| 1.5 | **Wildcard tenant routing** — `*.spstechnosoft.com` DNS + wildcard ACM + Host→tenant edge resolution + Host↔JWT cross-check + reserved-subdomain blocklist | Tenancy & Routing spec; deferred as STOP-4 paid infra |
| 1.6 | **DKIM records** (Microsoft 365 CNAMEs at GoDaddy) | SPF live, DKIM missing → deliverability risk |
| 1.7 | **Rate-limit public registration** (Redis token bucket on `/api/register/*`) | Recommended before real signups |

### 🟠 P2 — Staffing MVP gaps (spec'd for P2, not yet built)
| # | Task | Notes |
|---|------|-------|
| 2.1 | **Resume upload → S3** — presigned PUT, key convention, size/type validation; wire erasure S3 delete (`s3:DeleteObject` + fix `storage_bucket` default mismatch) | Column exists, no writer code |
| 2.2 | **Resume parsing + JD parsing** (`POST /jobs/{id}/parse-jd`, skill extraction with weightage) | Prerequisite for assessments & matching |
| 2.3 | **JD-driven assessment engine** — rule engine (exp→count/difficulty), question bank, weighted random selection, candidate email link, auto-evaluation, per-skill scorecard | Appendix A; flagship differentiator, entirely unbuilt |
| 2.4 | **Notification service** — SES email (DKIM first), versioned templates, queue + retry + idempotency, delivery tracking; then invite-link/set-password emails for approved clients & teammates | Nothing sends email today; admin sets passwords inline |
| 2.5 | **Candidate timeline** — append-only `candidate_timeline` event store + profile timeline UI | Not built |
| 2.6 | **Duplicate detection (fuzzy + merge)** — pg_trgm fuzzy match, review queue, merge workflow with reversible audit | Exact-match dedup (blind index 409) exists; fuzzy/merge don't |
| 2.7 | **Search** — Postgres FTS (`search_doc` tsvector + GIN) over candidates/jobs/clients, keyword + structured filters | Not built |
| 2.8 | **Public job board** `/jobs` on marketing site (SSR + filters) + careers page real data (currently sample/demo jobs) | Spec P1/P2 item |
| 2.9 | **Reporting read-models** — nightly aggregation jobs (recruiter/client/revenue/candidate metrics), CSV/Excel/PDF exports; fix `me/overview` hardcoded zeros (`TODO Slice 3`) | Dashboards must read read-models, never OLTP |
| 2.10 | **Founder dashboard** — revenue/ops/recruiter/compliance/system-health panels (Redis-cached, audited) | Not built |
| 2.11 | **Admin dashboard page** — replace static placeholder with real KPI widgets | `/admin/dashboard` is a stub |
| 2.12 | **CRM module** — leads pipeline (new→qualified→proposal→negotiation→won/lost), activities, tasks, convert | In MVP scope per spec; not built |
| 2.13 | **Auth hardening** — forgot-password flow, TOTP MFA for staff/admin, account lockout, HIBP password check | In frontend build spec; absent |
| 2.14 | **E-sign workflow** — RTR / offer acceptance e-sign with immutable audit | Offers store RTR flag only |
| 2.15 | **Invoice GST/TDS compliance** — statutory rates, rounding, place-of-supply, HSN/SAC, invoice numbering, PDF generation | Gated on legal answers (Q1) |
| 2.16 | **Marketing contact form backend** — currently validates + fakes success, sends nothing; also real WhatsApp number in chat widget | Quick win once email/notifications exist |
| 2.17 | **Staff nav for legacy `/employer/*` screens** + hide Team/Offers nav from `client_manager` | Small UX debts from client-portal work |

### 🟡 P3 — Compliance follow-ups (gated on legal answers)
| # | Task | Notes |
|---|------|-------|
| 3.1 | Resolve open legal Qs: retention floor (Q1), audit-log identifiers (Q3), legal-hold definition (Q5), erasure SLA/approval (Q6), consent survival (Q7) | SPS_DPDP_Legal_Brief.md exists at repo root as input |
| 3.2 | Implement erasure auto-purge (timed hard-delete) + real legal-hold rule once Qs answered | Deliberate inert stub today |
| 3.3 | Uphold "no PII in Redis" invariant on any future caching | Standing constraint, not a bug |

### 🟢 P4 — Production readiness (spec P3)
| # | Task | Notes |
|---|------|-------|
| 4.1 | Staging + prod environments (Terraform), multi-AZ RDS, WAF, `main` deploy target with gated migrations (required reviewers) | UAT/prod CI job is a commented stub |
| 4.2 | GitHub branch protection (deferred until dev E2E validated with UI) | |
| 4.3 | Monitoring/alarms — 5xx, p95 latency, RDS CPU/connections, queue depth; structured-log dashboards | |
| 4.4 | DR drill — timed restore from snapshots, documented runbook (RPO 15 min / RTO 2 h target) | |
| 4.5 | Fix Terraform `backend_image_tag` landmine (plain `apply` regresses live image) + migrate to S3 `use_lockfile`, drop DynamoDB table | C3/C4 |
| 4.6 | CI OIDC retry-storm fix (bound retries); GST number on AWS tax settings | E4/E3 |

### 🔵 P5 — SaaS layer (spec P9 / Tenancy doc; models exist, flows don't)
- Tenant self-serve signup (`/api/tenants/signup`) → auto-provision tenant + BUs + owner.
- Billing: Razorpay Subscriptions, plan gates (`require_quota` → 402), usage metering.
- Tenant theming/white-label (`tenant_branding` → CSS variables).
- Marketing SSG-per-locale for SEO (`app/[locale]/` + hreflang) — currently cookie-i18n forces dynamic rendering.

### ⚪ P6 — Later phases (per roadmap, after Staffing launch)
- **Academy vertical** (P4): courses, cohorts, enrolment + Razorpay payment flow, certificates, student portal.
- **Consulting vertical** (P5): engagements, allocations, timesheets, milestones, burn reports.
- **Vendor depth** (V2): vendor_contracts, commissions calc/payout, performance, vendor-submission creation UI.
- **Real AI** (P8): replace deterministic stubs — resume scoring, JD generator, ranking, copilot; PII redaction + cost caps.
- i18n beyond en+hi (spec names 32 locales) and beyond marketing pages.

---

## Suggested immediate sequence (next 2–3 working sessions)
1. **1.3** dev login working end-to-end on dev-api (small, unblocks demos).
2. **1.4** frontend deploy target + CI (biggest visibility win — nothing is publicly viewable today).
3. **1.1 + 1.2** legal copy + hCaptcha keys (unblocks real signups).
4. **1.6 → 2.4** DKIM, then SES notification service (unblocks invites, contact form, assessment emails).
5. **2.1** resume upload (unblocks parsing → assessments chain).
