# SPS Staffing — Build Log

Chronological journal of infrastructure work. Newest entries appended at the
bottom of the dated sections. Updated at the end of **every** session.

---

## 2026-06-26 — Backfill: work to date

### Email migration — spstechnosoft.com DNS → GoDaddy
- Moved DNS for `spstechnosoft.com` off **AWS Route 53** (old account) to **GoDaddy** nameservers `ns35.domaincontrol.com` / `ns36.domaincontrol.com`.
- Added **MX** → `spstechnosoft-com.mail.protection.outlook.com` (priority 0) and **SPF TXT** for Microsoft 365.
- Verified with `dig`; mail confirmed flowing.
- **Status:** ✅ Live. ⚠️ DKIM CNAMEs still pending.

### AWS account
- Created account **SPS-Staffing**, ID `412058343855`.
- Root = `priyanka@spstechnosoft.com`, Business/Company type, region **Mumbai (ap-south-1)**.
- Root secured with **MFA**, **no access keys**.
- Alternate contacts set to `awsstaffing@spstechnosoft.com`.
- **Status:** ✅ Active, root secured.

### IAM users
- `priyanka-admin` — console access, MFA, `AdministratorAccess`.
- `priyanka-cli-admin` — programmatic access, `AdministratorAccess`, access key on Sandeep's Mac under CLI profile `sps`.
- **Status:** ✅ Active.

### Terraform backend
- S3 bucket `sps-staffing-tfstate-412058343855` — versioned, encrypted, public access blocked.
- DynamoDB lock table `sps-staffing-tflock` — **ACTIVE**.
- Backend currently uses `dynamodb_table`. ⚠️ Deprecation warning noted; plan to migrate to `use_lockfile = true` and delete the table later.
- **Status:** ✅ Initialized and in use.

### Billing
- Cost Explorer enabled.
- Two budgets `sps-monthly-cost-A` and `sps-monthly-cost-B`, **$50/mo** ceiling, alerts at 1% then every 10% to 100%, emailing `awsstaffing@spstechnosoft.com`.
- **Status:** ✅ Both confirmed in console.

### VPC networking layer (applied)
- VPC `vpc-02fb59e64ece1b044`, CIDR `10.0.0.0/16`, **2 AZs** (ap-south-1a / ap-south-1b).
- Public subnets: `subnet-077e276f551322de4` / `subnet-0af60d363e711dcb3` (ALB + NAT).
- Private-app subnets: `subnet-05432e3bb9a904a32` / `subnet-040690876c20f8ff9` (ECS Fargate).
- Private-data subnets: `subnet-06a939f839e830a27` / `subnet-0a2c221c03092bdc5` (RDS + Redis).
- Internet gateway + single NAT gateway `nat-0790278510f6041e9` (~$32/mo, dev cost-saver).
- Route tables: public→IGW, both private tiers→NAT.
- **18 resources** added (`terraform apply`, 0 changed / 0 destroyed).
- Files: `vpc.tf`, `outputs.tf`.
- **Status:** ✅ Applied, state in S3 backend.

### Security groups (planned, awaiting apply)
- Wrote `security_groups.tf` with four SGs in `vpc-02fb59e64ece1b044`:
  - `sps-staffing-dev-alb-sg` — ingress TCP 80 + 443 from `0.0.0.0/0`, egress all.
  - `sps-staffing-dev-ecs-sg` — ingress `var.container_port` (default **8000**) from ALB SG, egress all.
  - `sps-staffing-dev-rds-sg` — ingress TCP 5432 from ECS SG only, egress all.
  - `sps-staffing-dev-redis-sg` — ingress TCP 6379 from ECS SG only, egress all.
- Added `var.container_port` (default 8000) to `variables.tf`.
- Rules use separate `aws_security_group_rule` resources (SG-to-SG, avoids cycles).
- Added 4 SG-ID outputs to `outputs.tf`.
- `terraform fmt` / `validate` clean; `terraform plan` = **13 to add, 0 to change, 0 to destroy**.
- **Status:** 🟡 Planned, awaiting apply (not yet applied).

### Security groups (applied)
- Applied `security_groups.tf` — **13 added, 0 changed, 0 destroyed** (`terraform apply`).
- Resulting security group IDs (in `vpc-02fb59e64ece1b044`):
  - `sps-staffing-dev-alb-sg` → `sg-0de4350511c1539e0`
  - `sps-staffing-dev-ecs-sg` → `sg-07797f1f6db25e1d2`
  - `sps-staffing-dev-rds-sg` → `sg-0798ca8f5fffa1d6d`
  - `sps-staffing-dev-redis-sg` → `sg-092c7e2be0ee3f729`
- **Status:** ✅ Applied, state in S3 backend. (Supersedes the 🟡 planned entry above.)

### RDS PostgreSQL data layer (planned, awaiting apply)
- Wrote `rds.tf` — RDS PostgreSQL in the two private-data subnets, reachable only from the ECS SG (`sg-07797f1f6db25e1d2`).
  - Instance `sps-staffing-dev-rds` — engine `postgres` v16, **db.t4g.small**, **Single-AZ** (`multi_az = false`; flip to true for prod Multi-AZ HA).
  - Storage: 20 GB gp3, `max_allocated_storage = 100` (autoscaling cap), `storage_encrypted = true`.
  - DB subnet group `sps-staffing-dev-rds-subnet-group` across both private-data subnets.
  - `db_name = sps_staffing_dev` (underscores — Postgres connection-string safe), master user `spsadmin`.
  - `backup_retention_period = 7`, `deletion_protection = true`, `skip_final_snapshot = false`, `final_snapshot_identifier = sps-staffing-dev-rds-final`, `apply_immediately = true`, `publicly_accessible = false`.
  - Master password generated via `random_password` (length 32, excludes `/ @ "` and space) and stored in **Secrets Manager** secret `sps-staffing-dev-rds-credentials` (JSON: username/password/host/port/dbname). Password is never output.
- Added `random` provider to `providers.tf`; `terraform init` re-run to install it.
- Added vars to `variables.tf`: `db_instance_class`, `db_engine_version`, `db_allocated_storage`, `db_name`, `db_username`.
- Added outputs: `rds_endpoint` (sensitive), `rds_port`, `rds_secret_arn` (sensitive). No password output.
- Cost-control helpers: `scripts/db-stop.sh` / `scripts/db-start.sh` (executable; identifier derived from TF naming; stop script warns AWS auto-restarts after 7 days).
- No schemas created in TF — default `public` schema left to the app migration layer (see DECISIONS: tenant-isolation deferred).
- `terraform fmt` / `validate` clean; `terraform plan` = **5 to add, 0 to change, 0 to destroy**.
- **Cost:** ~$25/mo running / ~$3/mo stopped (storage only).
- **Status:** 🟡 Planned, awaiting apply (not yet applied).

### RDS PostgreSQL data layer (applied)
- Applied `rds.tf` — **5 added, 0 changed, 0 destroyed** (`terraform apply`, instance provisioning took ~7m19s).
- Instance `sps-staffing-dev-rds` (Single-AZ, db.t4g.small, postgres 16, 20 GB gp3, encrypted).
- **Endpoint:** `sps-staffing-dev-rds.c72e00mua48f.ap-south-1.rds.amazonaws.com:5432`
- **Secret ARN:** `arn:aws:secretsmanager:ap-south-1:412058343855:secret:sps-staffing-dev-rds-credentials-gWl1uO` (master credentials + connection JSON; password stored here only, never output).
- Isolation verified from state:
  - `vpc_security_group_ids = [sg-0798ca8f5fffa1d6d]` (rds SG only — reachable only from ECS app tier).
  - DB subnet group spans the two private-data subnets (`subnet-06a939f839e830a27`, `subnet-0a2c221c03092bdc5`).
- `db_name = sps_staffing_dev`, `deletion_protection = true`, `backup_retention_period = 7`, `final_snapshot_identifier = sps-staffing-dev-rds-final`.
- **Cost:** ~$25/mo running / ~$3/mo stopped — use `scripts/db-stop.sh` / `db-start.sh` to pause (auto-restarts after 7 days).
- **Status:** ✅ Applied, state in S3 backend. (Supersedes the 🟡 planned entry above.)

### Redis (ElastiCache) data layer (planned, awaiting apply)
- Wrote `redis.tf` — single-node Redis in the two private-data subnets, reachable only from the ECS SG (`sg-07797f1f6db25e1d2`) via the redis SG (`sg-092c7e2be0ee3f729`).
  - Replication group `sps-staffing-dev-redis` — engine `redis` v7.1, **cache.t4g.micro**, **single node** (`num_cache_clusters = 1`, `automatic_failover_enabled = false`, `multi_az_enabled = false`; raise for prod HA).
  - Subnet group `sps-staffing-dev-redis-subnet-group` across both private-data subnets (`subnet-06a939f839e830a27`, `subnet-0a2c221c03092bdc5`).
  - Port 6379, `at_rest_encryption_enabled = true`, `transit_encryption_enabled = false` (dev — TLS forces rediss:// client complexity; prod should enable).
  - `auto_minor_version_upgrade = true`, maintenance window `sun:05:00-sun:06:00`, `apply_immediately = true`.
- Added vars to `variables.tf`: `redis_node_type` (cache.t4g.micro), `redis_engine_version` (7.1).
- Added outputs: `redis_endpoint` (sensitive), `redis_port`.
- `terraform fmt` / `validate` clean; `terraform plan` = **2 to add, 0 to change, 0 to destroy**.
- **Cost:** ~$11/mo. ⚠️ ElastiCache **cannot be stopped** like RDS — cost lever is node size or `terraform destroy` of this layer when idle (cache/broker data only, safe to recreate). See DECISIONS.
- **Status:** 🟡 Planned, awaiting apply (not yet applied).

### Rename shared layer to `sps-shared-dev-*` convention + `sps_platform_dev` DB (planned)
- Adopted the canonical naming + tenancy convention (see DECISIONS): shared platform layer = `sps-shared-dev-*` tagged `Vertical = shared`; per-vertical = `sps-staffing|edtech|itservice-dev-*`. Common tags `Project = sps`, `Environment = dev`, `ManagedBy = terraform` (+ per-resource `Vertical`).
- Changed `local.name_prefix` → `sps-shared-${var.environment}`; provider `default_tags` `Project` → `sps`; added `Vertical = "shared"` to every shared resource.
- DB: `var.db_name` default `sps_staffing_dev` → **`sps_platform_dev`** (one shared DB; schemas shared/staffing/academy/consulting created later by Alembic, not TF).
- Renamed: RDS instance/subnet-group/secret/final-snapshot, all 4 SGs, VPC layer Name tags → `sps-shared-dev-*`. Redis (`redis.tf`, never applied) is created fresh under `sps-shared-dev-redis`. Updated `scripts/db-stop.sh`/`db-start.sh` identifier → `sps-shared-dev-rds`. `outputs.tf` unchanged (attribute-based, no hardcoded names).
- `terraform fmt` / `validate` clean; `terraform plan` = **19 to add, 12 to change, 17 to destroy**.
  - **12 change (in-place, NO replacement):** VPC, IGW, EIP, NAT, 2 route tables, 6 subnets — only Name/Project/Vertical tags update. **VPC + subnet + NAT IDs are preserved.**
  - **17 destroy + 17 of the 19 adds = replacements:** 4 SGs + 9 SG rules (SG `name`/ID is create-only), RDS instance (`identifier` + `db_name` force replacement), RDS subnet group, Secrets Manager secret + secret version. The remaining **2 adds = Redis** (subnet group + replication group, fresh).
  - **RDS replacement is the EMPTY instance** — provisioned but never loaded (no app/ECS, no schemas yet). **No data loss.**
- ⚠️ **deletion_protection kept `true` in the file** (end state protected). The plan succeeds, but **apply's destroy of the old protected instance requires disabling protection first via CLI** (chosen over a file-flip + second apply):
  ```
  aws rds modify-db-instance --db-instance-identifier sps-staffing-dev-rds \
    --no-deletion-protection --apply-immediately --profile sps --region ap-south-1
  ```
  The new `sps-shared-dev-rds` comes up with protection on (from the file). `skip_final_snapshot = false` → a final snapshot of the empty DB is taken on destroy.
- **Status:** 🟡 Planned, awaiting apply (not yet applied). Apply will recreate RDS (~7 min) and create Redis.

### Rename shared layer + Redis (applied)
- Disabled deletion protection on the old `sps-staffing-dev-rds` via CLI (confirmed `DeletionProtection=False`), then `terraform apply` — **19 added, 12 changed, 17 destroyed**. RDS replacement took ~6m37s; Redis created in ~4m35s.
- Networking retagged in-place (IDs preserved): VPC `vpc-02fb59e64ece1b044`, NAT `nat-0790278510f6041e9`, all 6 subnets — now `sps-shared-dev-*`, `Project = sps`, `Vertical = shared`.
- **New security group IDs** (all replaced):
  - `sps-shared-dev-alb-sg` → `sg-004fd8c732a6d7481`
  - `sps-shared-dev-ecs-sg` → `sg-0424036eccfe6c626`
  - `sps-shared-dev-rds-sg` → `sg-0073fe175ed64e984`
  - `sps-shared-dev-redis-sg` → `sg-0dbeacb3272c1face`
- **New RDS** `sps-shared-dev-rds` (replaced the empty instance; no data loss):
  - **Endpoint:** `sps-shared-dev-rds.c72e00mua48f.ap-south-1.rds.amazonaws.com:5432`
  - **DB name:** `sps_platform_dev` (one shared DB; schemas created later by Alembic).
  - **deletion_protection = true** ✅ confirmed (came up protected from the file).
  - **Secret ARN:** `arn:aws:secretsmanager:ap-south-1:412058343855:secret:sps-shared-dev-rds-credentials-FG2D47` (new; old `…-gWl1uO` scheduled for deletion).
- **New Redis** `sps-shared-dev-redis` (single-node cache.t4g.micro, redis 7.1):
  - **Endpoint:** `sps-shared-dev-redis.osj3uw.ng.0001.aps1.cache.amazonaws.com:6379`
- **Status:** ✅ Applied, state in S3 backend. (Supersedes the 🟡 planned rename + Redis entries above.)

### Compute tier Phase 1 — backend app folder + ECR + image build/push (applied)
- **Canonical backend app folder:** copied `Context/spstechnosoft-platform/backend/` → `~/Staffing and Recruitment/backend/` (sibling of `Project/`). Context copy stays read-only reference. (See DECISIONS.)
- **Deterministic build fixes** (no app-logic change; `/healthz` still 200 with no DB):
  - `pyproject.toml`: added `[build-system]` (setuptools≥68 + wheel) and `[tool.setuptools.packages.find] include = ["app*"]`.
  - `Dockerfile`: copy source before `pip install -e .` (flat layout), non-root `appuser` (uid 10001), python:3.12-slim, EXPOSE 8000, uvicorn CMD unchanged.
  - Added `.dockerignore`.
- **Local verify:** `docker build` clean; container smoke test `GET /healthz` → 200 `{"status":"ok","env":"dev","region":"ap-south-1"}`, boots with no DB.
- **ECR (`ecr.tf`, applied — 2 added, 0 changed, 0 destroyed):**
  - Repo `sps-shared-dev-backend`, `MUTABLE`, `scan_on_push = true`, `Vertical = shared`.
  - Lifecycle policy: keep only the last 10 images.
  - Output `ecr_repository_url`.
- **Image pushed:**
  - **Repo URL:** `412058343855.dkr.ecr.ap-south-1.amazonaws.com/sps-shared-dev-backend`
  - **Tags:** `dev` and `dev-20260626-175843` (same image)
  - **Digest:** `sha256:f4cbd0e2f937243b404fe1181c2ded8fd793055bb12a66dbd4e3ea2b29c09e60`
  - ⚠️ **Image architecture = `arm64/linux`** (built on Apple Silicon). The ECS task definition MUST set `runtime_platform { cpu_architecture = "ARM64" }` (Graviton/Fargate ARM64) — consistent with our `t4g` choices — OR the image must be rebuilt `--platform linux/amd64`. Default Fargate (X86_64) will NOT run this image. (See DECISIONS.)
- **Status:** ✅ Applied & pushed. (ECR + image live; ECS/ALB not yet created.)

### Compute tier Phase 2 — ECS Fargate + ALB (planned, awaiting apply)
- Wrote `alb.tf` + `ecs.tf` wiring the pushed image `sps-shared-dev-backend:dev` (ARM64) live behind a load balancer.
  - **ALB** `sps-shared-dev-alb` — internet-facing, in the 2 public subnets, alb SG (`sg-004fd8c732a6d7481`). Listener **HTTP:80** → target group. (HTTPS:443 + ACM deferred to a follow-up once an in-region cert exists.)
  - **Target group** `sps-shared-dev-backend-tg` — `target_type = ip` (Fargate awsvpc), port 8000, HTTP, health check **`/healthz`**, healthy threshold 2, interval 30s, matcher 200.
  - **ECS cluster** `sps-shared-dev-cluster` (Container Insights on).
  - **IAM:** execution role `sps-shared-dev-ecs-execution-role` (+ `AmazonECSTaskExecutionRolePolicy`); task role `sps-shared-dev-ecs-task-role` (no policies yet — where Secrets Manager/S3 perms attach later).
  - **Log group** `/ecs/sps-shared-dev-backend`, retention 14 days.
  - **Task def** `sps-shared-dev-backend` — FARGATE/awsvpc, cpu 256 / mem 512, **`runtime_platform { ARM64, LINUX }`** (required — image is arm64), container `backend` image `:dev`, port 8000, awslogs, env `APP_ENV=dev` + `AWS_REGION=ap-south-1` (no DB needed to boot).
  - **Service** `sps-shared-dev-backend` — FARGATE, desired_count 1, **private-app subnets** + **ecs SG** (`sg-0424036eccfe6c626`), `assign_public_ip = false` (ECR/logs via NAT), load_balancer → target group, health_check_grace 60s, depends_on the listener.
- Added vars: `backend_image_tag` (dev), `backend_cpu` (256), `backend_memory` (512), `backend_desired_count` (1). Output `alb_dns_name`.
- Cost helper `scripts/ecs-scale.sh <0|1>` to pause/resume Fargate (notes ALB stays billing).
- `terraform fmt` / `validate` clean; `terraform plan` = **10 to add, 0 to change, 0 to destroy**.
- **Cost:** ALB ~$16/mo (always-on, not paused by scaling) + Fargate ~$9/mo if 1 task runs 24/7 (pause via `ecs-scale.sh 0`).
- **Status:** 🟡 Planned, awaiting apply (not yet applied).

### Compute tier Phase 2 — ECS Fargate + ALB (applied)
- Applied `alb.tf` + `ecs.tf` — **10 added, 0 changed, 0 destroyed**. Backend is live end-to-end.
- **ALB DNS:** `sps-shared-dev-alb-651499533.ap-south-1.elb.amazonaws.com` (HTTP:80).
- **Target group** `sps-shared-dev-backend-tg` (`/997ed67ca704d462`) — task registered **healthy** in ~30s after task start (health check `/healthz` on 8000).
- **End-to-end verified:** `GET http://<alb_dns>/healthz` → **200** `{"status":"ok","env":"dev","region":"ap-south-1"}`. (`/api/whoami` also responds; tenant resolves from Host as designed.)
- Service `sps-shared-dev-backend` running 1 ARM64 task (256/512) in private-app subnets, ecs SG, no public IP (ECR/logs via NAT). Logs in `/ecs/sps-shared-dev-backend`.
- **Cost now live:** ALB ~$16/mo (always-on) + Fargate ~$9/mo @ 1 task 24/7. Pause Fargate with `scripts/ecs-scale.sh 0`.
- **Status:** ✅ Applied, state in S3 backend. (Supersedes the 🟡 planned entry above.)

### HTTPS for dev-api.spstechnosoft.com — Stage 1 (planned, awaiting GoDaddy DNS + apply)
- Wrote `acm.tf`: `aws_acm_certificate.main` for `dev-api.spstechnosoft.com` (DNS validation, `create_before_destroy`, `Vertical = shared`) + `aws_acm_certificate_validation.main` (blocks until the GoDaddy CNAME is added and ACM issues).
- Updated `alb.tf`: new **HTTPS:443** listener (`ELBSecurityPolicy-TLS13-1-2-2021-06`, cert from the validation resource, forward → backend TG); existing **HTTP:80** listener flipped `forward` → **301 redirect to 443**. Both `depends_on` the validation resource so neither applies before the cert is ISSUED.
- Added outputs `acm_validation_record_{name,type,value}` (the GoDaddy CNAME) — **known only after the cert is created**.
- `terraform fmt` / `validate` clean; `terraform plan` = **3 to add, 1 to change, 0 to destroy** (add: cert, validation, https listener; change: http listener → redirect).
- ⚠️ **Blocker / sequencing:** ACM validation values don't exist until the cert is requested, so a pure plan shows them `(known after apply)`. To reveal the exact GoDaddy CNAME, a **targeted apply of just `aws_acm_certificate.main`** is needed (free, requests the cert, validates nothing, touches no listeners). Then add the CNAME at GoDaddy → cert issues → Stage 2 full apply creates the 443 listener + flips 80 to redirect.
- **GoDaddy records needed:** (1) ACM validation CNAME (from the outputs after the cert is requested); (2) `dev-api` CNAME → `sps-shared-dev-alb-651499533.ap-south-1.elb.amazonaws.com`.
- **Cert requested** (`terraform apply -target=aws_acm_certificate.main` — cert only, no listeners): `dev-api.spstechnosoft.com`, status **PENDING_VALIDATION**.
  - **ACM validation CNAME to add at GoDaddy:** Host `_eb12ad850aa4cce6b048111212babcc0.dev-api` → Value `_7e92571556d8b8f5ef4f4ec8e21774e4.jkddzztszm.acm-validations.aws` (type CNAME).
  - **App CNAME to add at GoDaddy:** Host `dev-api` → Value `sps-shared-dev-alb-651499533.ap-south-1.elb.amazonaws.com`.
- **Stage 2 apply attempted 2026-06-26 — BLOCKED & rolled back cleanly.** Full apply was run on the belief the cert was ISSUED, but ACM still reports **PENDING_VALIDATION**. `aws_acm_certificate_validation.main` blocked (~10 min) with `waiting for ACM Certificate … to be issued`; apply gracefully interrupted. **No infra changed** (ALB still HTTP:80/forward), state lock released.
  - Root cause: querying GoDaddy's authoritative NS (`ns35.domaincontrol.com`) directly returns **no answer** for either the ACM validation CNAME or `dev-api` — i.e. **neither GoDaddy record is in place** (not a propagation issue; the authoritative server has no such records).
  - Resolution path: add both CNAMEs at GoDaddy (validation Host = `_eb12ad850aa4cce6b048111212babcc0.dev-api`; app Host = `dev-api` → ALB) → confirm via `dig @ns35.domaincontrol.com` → poll ACM to ISSUED → then re-run Stage 2 (fast once issued).
- **Stage 2 apply attempted 2026-06-26 — BLOCKED & rolled back cleanly.** Full apply was run on the belief the cert was ISSUED, but ACM still reported **PENDING_VALIDATION**. `aws_acm_certificate_validation.main` blocked (~10 min); apply gracefully interrupted. **No infra changed**, state lock released. Root cause: GoDaddy CNAMEs were not actually saved (authoritative NS returned no answer).

### HTTPS for dev-api.spstechnosoft.com (applied) ✅
- GoDaddy CNAMEs added & verified at `ns35.domaincontrol.com` (validation CNAME + `dev-api` → ALB). ACM cert reached genuine **ISSUED** (~11.5 min after DNS went live), cert `…/290cffe9-f317-44df-9ce8-751c5f7904c9`.
- Stage 2 full apply — **2 added, 1 changed, 0 destroyed** (validation resource + HTTPS:443 listener added; HTTP:80 listener changed forward → 301 redirect). The cert itself was already created via the earlier targeted apply.
- **Verified end-to-end:**
  - `GET https://dev-api.spstechnosoft.com/healthz` → **200**, body `{"status":"ok","env":"dev","region":"ap-south-1"}`, **valid TLS** (`ssl_verify_result=0`, subject `CN=dev-api.spstechnosoft.com`, issuer `Amazon RSA 2048 M01`).
  - `GET http://dev-api.spstechnosoft.com/healthz` → **301 Moved Permanently**, `Location: https://dev-api.spstechnosoft.com:443/healthz`.
- ALB: HTTPS:443 (`ELBSecurityPolicy-TLS13-1-2-2021-06`) forwards to backend TG; HTTP:80 redirects to 443.
- **Status:** ✅ Applied — backend live over HTTPS at `https://dev-api.spstechnosoft.com`.

### App ↔ data wiring (connection capability only — NO migrations) (planned, awaiting apply)
- **Safety preserved:** `/healthz` left byte-for-byte dependency-free (ECS health check). All DB/Redis access is lazy (created on first use, never at import/startup). Verified locally: new image boots with DB/Redis unreachable → container stays **Up**, `/healthz` → **200**, new `/readyz` → **503** `{"db":"error: OperationalError","redis":"error: ConnectionError"}`.
- **App code** (`backend/`, image rebuilt + pushed):
  - `config.py`: reads `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` + `REDIS_HOST/REDIS_PORT` with safe localhost defaults (boots if absent).
  - `app/db.py` (new): lazy SQLAlchemy engine + Redis client (no connect at import; 3s connect timeouts) + `check_db()` (SELECT 1) / `check_redis()` (PING).
  - `main.py`: added `/readyz` (deep DB+Redis probe, 503 if down) — **NOT** wired to the ECS health check. `/healthz` unchanged.
  - No models/migrations/schema — connection capability only. `alembic/` untouched.
  - New image tag **`dev-20260626-193851`**, digest `sha256:231727c69cd9574708c2d105cccbaeeb5ec70930e1967b12d9d3f8cfc5526cec` (pushed to ECR, also re-tagged `:dev`).
- **Terraform** (`ecs.tf`, `variables.tf`):
  - IAM (least privilege): `secretsmanager:GetSecretValue` on the `sps-shared-dev-rds-credentials` ARN only — added to **task role** (runtime boto3) and **execution role** (resolves the task-def `secrets` block).
  - Task def env: `DB_HOST` (RDS endpoint), `DB_PORT=5432`, `DB_NAME=sps_platform_dev`, `REDIS_HOST` (Redis primary), `REDIS_PORT=6379`. Secrets: `DB_USER`/`DB_PASSWORD` via `valueFrom` `…:username::` / `…:password::`.
  - Image tag → `dev-20260626-193851`. CPU/memory/port/health-check path unchanged.
- `terraform fmt` / `validate` clean; `terraform plan` = **3 to add, 1 to change, 1 to destroy**.
  - add: 2 IAM role policies + new task-def revision. change: ECS service (in-place, rolls to new revision). destroy: **old task-def revision deregistered** (normal — task defs are immutable; not infra loss).
  - **No destroys of VPC/SG/RDS/Redis/ALB/ECR.**
- **Status:** 🟡 Planned (superseded by the applied entry below).

### App ↔ data wiring (connection capability only) (applied) ✅
- Applied — IAM policies created, new task-def revision registered, service rolled to it. **3 added, 1 changed, 1 destroyed** (the 1 destroyed = old task-def revision deregistered).
- Rollout verified end-to-end against `https://dev-api.spstechnosoft.com`:
  - `/healthz` stayed **200** through the entire rollout (ECS health never failed).
  - `/readyz` returned **404** while the old task served (endpoint didn't exist yet), then **200** once the new task registered (~50s) → `{"status":"ready","db":"ok","redis":"ok"}`.
- Proves: execution role pulled `DB_USER`/`DB_PASSWORD` from Secrets Manager (no plaintext), env wiring correct, and ecs SG → rds SG (5432) / redis SG (6379) connectivity works. Image `dev-20260626-193851`.
- **Status:** ✅ Applied — backend connects to RDS + Redis; `/healthz` remains dependency-free.

### Alembic + four schemas (run-once migration task) (planned, awaiting apply) 🟡
- **Migrations never run at app startup.** `main.py` has no startup/lifespan hook; `/healthz` unchanged & dependency-free (re-verified on the new image: boots with no DB, `/healthz` 200). Migrations run ONLY via a deliberate, separate Fargate task.
- **Alembic configured in `backend/`:**
  - `alembic.ini` (script_location=alembic; URL set in env.py, not hardcoded), `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_create_schemas.py`.
  - `env.py` reads the DB URL from the app's `settings` (DB_HOST/PORT/NAME/USER/PASSWORD — same as runtime), sets **`version_table_schema = "shared"`**, and (online) `CREATE SCHEMA IF NOT EXISTS "shared"` before stamping (chicken-and-egg). `target_metadata = Base.metadata` (new `app/base.py`, imported only by Alembic, not app boot) so future autogenerate works.
  - Migration `0001_create_schemas`: `upgrade()` creates the four schemas `shared`/`staffing`/`academy`/`consulting` (`CREATE SCHEMA IF NOT EXISTS`); `downgrade()` drops them `RESTRICT` (cautious). **No tables/models.**
  - Verified in-image: `alembic heads` → `0001_create_schemas (head)`; files present.
- **New image** `dev-20260626-195327` (digest `sha256:881a3c6fe3a97c101d5a42e4eb9a93ef306ec833851849104e2fd3e02f50beff`) pushed (includes alembic config + migration); also re-tagged `:dev`.
- **Terraform (`migrate.tf`, `variables.tf`):**
  - `aws_ecs_task_definition.migrate` (`sps-shared-dev-migrate`): same image/roles/ARM64, **`command = ["alembic","upgrade","head"]`**, DB env + DB_USER/DB_PASSWORD secrets, logs to new `/ecs/sps-shared-dev-migrate`. **Run-once — NOT a service.**
  - `scripts/run-migration.sh`: runs the task in private-app subnets + ecs SG (no public IP), waits, reports exitCode + logs.
  - Image tag bumped → `dev-20260626-195327` (used by both backend service + migrate task).
- `terraform fmt` / `validate` clean; `terraform plan` = **3 to add, 1 to change, 1 to destroy**.
  - add: migrate task-def + migrate log group + new backend task-def revision. change: backend service (in-place) — **image-only** (`…193851 → …195327`), confirmed no command/startup-migration/healthz change. destroy: old backend task-def revision (deregistered — normal).
  - **No destroys of VPC/SG/RDS/Redis/ALB/ECR.** No migration has run yet.
- **Apply done (2026-06-26):** **3 added, 1 changed, 1 destroyed** — migrate task def `sps-shared-dev-migrate` + log group `/ecs/sps-shared-dev-migrate` registered; backend service rolled to task-def **rev 3** (image `dev-20260626-195327`). Clean roll verified: `/healthz` stayed 200, `/readyz` → `{"db":"ok","redis":"ok"}` on the new image.
- **Status:** 🟢 Infra applied; ⏸️ **migration NOT yet run** — schemas do not exist yet. Run `scripts/run-migration.sh` (separately, on approval) to create the four schemas.

### Migration attempt #1 — FAILED (env.py ConfigParser bug), fixed & re-staged
- Ran `scripts/run-migration.sh` → migrate task **exit code 1**. Failed at `env.py` load, **before any DB DDL** — so **no schemas were created**; data tier untouched; running service unaffected (service never runs alembic).
- **Root cause:** `env.py` set the URL via `config.set_main_option(...)`, routing it through Python ConfigParser; the generated RDS password contains `%`, which ConfigParser misreads as interpolation → `ValueError: invalid interpolation syntax`. Not the chicken-and-egg, not secret/SG wiring (URL was fully assembled with the real password).
- **Fix:** `env.py` now builds the engine directly with `create_engine(settings.database_url)` (no ConfigParser) — same path the running app/`/readyz` already uses successfully. Verified in-image: a `%`-laden password now reaches the connection step (psycopg OperationalError to an unreachable host) with no ConfigParser error.
- New fixed image **`dev-20260626-200719`** (digest `sha256:a879cc0129217649534925fa06ff2f6bf71503558b322c6389a3ba8ac9047fc1`) pushed (+ `:dev`). Bumped `var.backend_image_tag`.
- `terraform plan` = **2 to add, 1 to change, 2 to destroy** (new backend + migrate task-def revisions on the fixed image; service in-place image-only roll; 2 old task-def revisions deregistered). Not yet applied.
- **Status:** 🟡 Fix staged (superseded by the applied entry below).

### Alembic + four schemas (applied) ✅
- Applied fixed image `dev-20260626-200719` to both task defs (**2 added, 1 changed, 2 destroyed** — old task-def revisions deregistered). Service rolled clean: `/healthz` 200, `/readyz` `{"db":"ok","redis":"ok"}`.
- **Migration re-run via `scripts/run-migration.sh` → exit code 0.** Logs: `Running upgrade -> 0001_create_schemas`.
- **Positive proof** (one-off query task against `sps_platform_dev`):
  - `SCHEMAS=academy,consulting,shared,staffing` ✅ all four present.
  - `ALEMBIC_VERSION=0001_create_schemas` (stamped in the `shared` schema) ✅.
- No tables created (schemas only), per the schema-per-vertical model. App service unaffected throughout (migrations run only via the separate run-once task).
- **Status:** ✅ Applied — four schemas + `shared.alembic_version` at `0001` exist in `sps_platform_dev`.

### S3 storage bucket (planned, awaiting apply) 🟡
- Wrote `s3.tf` — shared file-upload bucket `sps-shared-dev-storage-412058343855` (`ap-south-1`, `Vertical = shared`) for resumes/candidate docs.
  - **Public access fully blocked** — all four flags true (`block_public_acls`/`block_public_policy`/`ignore_public_acls`/`restrict_public_buckets`); no bucket policy grants public access (DPDP — personal data).
  - **Encryption** at rest: SSE-S3 `AES256` (SSE-KMS noted as prod upgrade).
  - **Versioning** enabled; **lifecycle** aborts incomplete multipart uploads after 7 days.
  - **Task-role access scoped to THIS bucket only** (not `*`): `s3:Get/Put/DeleteObject` on `…/storage-…/*` + `s3:ListBucket` on the bucket ARN — `aws_iam_role_policy.task_s3_storage` on the existing ECS task role.
- Injected `S3_BUCKET` env var into the backend container (no image rebuild — env only; image tag unchanged). `/healthz` and startup untouched (no `command`, no DB/startup dependency added).
- Added outputs `s3_bucket_name`, `s3_bucket_arn`. Recorded the key-prefix convention + access model + DPDP residency in DECISIONS.
- `terraform fmt` / `validate` clean; `terraform plan` = **7 to add, 1 to change, 1 to destroy**.
  - add: bucket + public-access-block + SSE + versioning + lifecycle + S3 IAM policy + new backend task-def revision. change: backend service (in-place, env-only). destroy: old backend task-def revision (deregistered — normal).
  - **No destroys of VPC/SG/RDS/Redis/ALB/ECR.**
- **Status:** 🟡 Planned (superseded by the applied entry below).

### S3 storage bucket (applied) ✅
- Applied `s3.tf` — **7 added, 1 changed, 1 destroyed** (old backend task-def revision deregistered). Service now on task-def **rev 5** with the `S3_BUCKET` env var.
- Verified in AWS:
  - Bucket **exists**: `sps-shared-dev-storage-412058343855` (`arn:aws:s3:::sps-shared-dev-storage-412058343855`, region `ap-south-1`).
  - **Public access block — all four true**: `BlockPublicAcls`/`IgnorePublicAcls`/`BlockPublicPolicy`/`RestrictPublicBuckets`.
  - **Encryption**: `SSEAlgorithm = AES256`.
  - Versioning enabled; lifecycle aborts incomplete multipart @ 7d; task-role policy scoped to this bucket only.
  - Service rolled clean: `/healthz` 200, `/readyz` `{"db":"ok","redis":"ok"}`, desired 1 / running 1.
- Outputs: `s3_bucket_name = sps-shared-dev-storage-412058343855`, `s3_bucket_arn = arn:aws:s3:::sps-shared-dev-storage-412058343855`.
- **Status:** ✅ Applied — private, encrypted, versioned storage bucket live; app has `S3_BUCKET` + scoped task-role access.

### Migration 0002 — shared-schema spine (SQLAlchemy models) (planned, awaiting apply) 🟡
- **App code** (`backend/`): `app/mixins.py` (`TimestampMixin`, `TwoAxisMixin`, `BUSINESS_UNITS`/`business_unit_check` — for future vertical tables), `app/models.py` (7 spine models, all `schema='shared'`), `env.py` imports `app.models` for autogenerate. Models NOT imported at app startup → boot stays dependency-free (re-verified: `/healthz` 200, container Up; `alembic heads` → `0002_shared_spine`).
- **Migration `0002_shared_spine`** (chains after `0001_create_schemas`): autogenerated against scratch PG16, then hand-fixed — added `CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public`; `gen_random_uuid()` noted as PG16 built-in; renamed revision/file. Creates in `shared`: `tenants` (+`slug`), `business_units` (CHECK on code), `users` (citext email), `memberships`, `plans`, `tenant_subscriptions` (CHECK on status), `audit_logs` (bigserial, append-only — no mixin). Resolutions **A–E** per DECISIONS.
- **Local test (scratch PG16):** `alembic upgrade head` clean → 7 tables + `alembic_version=0002_shared_spine` in `shared`; `users.email` is `citext`; CHECK constraints present; **downgrade -1 → re-upgrade clean** (reversible).
- New image **`dev-20260626-213634`** (digest `sha256:e5c9fd84686bfb6ccc202ebe675e0e1b9a9e8f594adc5b653049b12df7ada005`) pushed (+ `:dev`). `var.backend_image_tag` bumped.
- `terraform plan` = **2 to add, 1 to change, 2 to destroy** (new backend + migrate task-def revisions; backend service in-place image roll; 2 old revisions deregistered). `/healthz`/startup untouched (image-only).
- **NOT applied; migration NOT run against RDS** (separate `scripts/run-migration.sh` step, later, on approval).
- **Status:** 🟡 Planned (superseded by the applied entry below).

### Migration 0002 — shared-schema spine (applied) ✅
- **Gate 1 — apply** (image roll to both task defs → `dev-20260626-213634`): **2 added, 1 changed, 2 destroyed**. Service rolled clean to task-def **rev 6** — `/healthz` 200, `/readyz` `{"db":"ok","redis":"ok"}`.
- **Gate 2 — migration against RDS** via `scripts/run-migration.sh` → **exit code 0**. Logs: `Running upgrade 0001_create_schemas -> 0002_shared_spine`.
- **Verified on the real database** (one-off query task): `SHARED_TABLES = alembic_version, audit_logs, business_units, memberships, plans, tenant_subscriptions, tenants, users` (all 7 spine tables ✅), `ALEMBIC_VERSION = 0002_shared_spine` ✅. Service unaffected: `/healthz` 200, `/readyz` green.
- **Status:** ✅ Applied — shared spine live in `sps_platform_dev.shared`.

### Migration 0003 — seed owner tenant SPS001 (planned, awaiting apply) 🟡
- **Migration `0003_seed_owner_tenant`** (chains after `0002_shared_spine`): idempotent **data** migration (Part 2 DoD). Seeds in `shared`: tenant `SPS001` (slug `sps`, "SPS Technosoft"); 3 business units (STAFFING/ACADEMY/CONSULTING); internal `plans` row (price 0, unlimited `-1` limits, all verticals + `all_features`); `tenant_subscriptions` SPS001→internal `active`; **password-less founder** `sandeep@spstechnosoft.com` (`status='invited'`, sentinel hash `!`); founder `memberships` in all 3 BUs with role `['owner']`.
- **No credentials in repo** — founder password set out-of-band via `scripts/set-founder-password.sh` (see DECISIONS). Idempotent: every INSERT `ON CONFLICT DO NOTHING` on natural keys; FKs resolved by lookup (no hardcoded UUIDs); `downgrade()` deletes seed rows by natural key.
- **Gotcha fixed:** JSONB literals with `:true`/colons (incl. in SQL comments) are mis-parsed by SQLAlchemy `text()` as bind params → rebuilt via `jsonb_build_object`/`jsonb_build_array` and scrubbed colon tokens from comments.
- **Local test (scratch PG16):** upgrade → `1,3,1,1,1,3` rows; founder `invited`+sentinel; plan jsonb correct; 3× `{owner}`. **Idempotency:** re-running the seed left counts unchanged. **Downgrade -1:** all zeros.
- New image **`dev-20260626-222817`** (digest `sha256:4924a5637d65c3120af88836f6c7abe87afb57e475f423f0a18c0cc9cb1ab205`) pushed (+`:dev`); alembic head `0003_seed_owner_tenant`. `var.backend_image_tag` bumped.
- `terraform plan` = **2 to add, 1 to change, 2 to destroy** (new backend + migrate task-def revisions; service in-place image roll; 2 old revisions deregistered). `/healthz`/startup untouched (image-only; re-verified boot 200 with no DB).
- **NOT applied; seed NOT run against RDS** (separate `scripts/run-migration.sh` step, later, on approval).
- **Status:** 🟡 Planned (superseded by the applied entry below).

### Migration 0003 — seed owner tenant SPS001 (applied) ✅
- **Gate 1 — apply** (image roll → `dev-20260626-222817`): service rolled clean to task-def **rev 7**; `/healthz` 200, `/readyz` `{"db":"ok","redis":"ok"}`.
- **Gate 2 — seed against RDS** via `scripts/run-migration.sh` → **exit code 0** (`0002_shared_spine -> 0003_seed_owner_tenant`).
- **Verified row data on real `sps_platform_dev`:**
  - `TENANT = ('SPS001','sps','SPS Technosoft')`
  - `BUS = [ACADEMY, CONSULTING, STAFFING]` (3 business units)
  - `PLAN = ('internal', 0, 'internal', {jobs/users/ai_calls:-1}, {verticals:[3], all_features:true})`
  - `SUB = ('active', plan_id set)`
  - `USER = ('sandeep@spstechnosoft.com','invited','Sandeep Kumar','!')` — **`PWCHECK=NOT_A_VALID_HASH_unusable`** (sentinel rejected by argon2; genuinely not a usable credential)
  - `MEMBERSHIPS = [ACADEMY, CONSULTING, STAFFING] each ['owner']`
  - `shared.alembic_version = 0003_seed_owner_tenant`
- Service unaffected: `/healthz` 200, `/readyz` green throughout.
- **Status:** ✅ Applied — owner tenant SPS001 seeded; founder password-less pending out-of-band `scripts/set-founder-password.sh`.

### Founder password set / account activated ✅
- Ran `scripts/set-founder-password.sh` (out-of-band, interactive) — set the founder password via argon2 (plaintext stayed in the terminal; only the hash reached the DB via the ECS env override; nothing in the repo). The helper's overrides-JSON assembly was fixed first to use `json.dumps` + `--overrides file://` (the prior hand-built JSON broke on the embedded Python's double quotes); hash still passed via env, never as a command arg, never printed.
- Verified read-only on `shared.users` for `sandeep@spstechnosoft.com`: **`status='active'`**, **`password_hash` starts with `$argon2id$`** (real hash; `IS_SENTINEL=False`). Full hash not printed — prefix only.
- **Status:** ✅ Founder owner account `sandeep@spstechnosoft.com` is now a usable, activated credential.

---

### Git branches + GitHub OIDC deploy role (planned, awaiting apply) 🟡
- **`develop` branch** created from `main` (both at `7b39811`) and pushed → tracking `origin/develop`. Branching model recorded in DECISIONS (develop→dev, main→prod). ⚠️ Default branch must be set to `develop` manually in the GitHub web UI (not a CLI action).
- **`oidc.tf`** (Terraform): GitHub Actions OIDC for keyless CI/CD deploys to dev:
  - `aws_iam_openid_connect_provider.github` — `token.actions.githubusercontent.com`, aud `sts.amazonaws.com`, GitHub thumbprints, `Vertical=shared`.
  - `aws_iam_role.sps-shared-dev-gha-deploy` — trust scoped to **`sub = repo:sps-tech-dev/sps-staffing:ref:refs/heads/develop`** (only this repo's develop branch) + aud `sts.amazonaws.com`.
  - Least-privilege deploy policy: ECR auth (`*`, unscopable) + push/pull scoped to the backend repo ARN; `ecs:RegisterTaskDefinition`/`DescribeTaskDefinition` (`*`, unscopable) + `UpdateService`/`DescribeServices` scoped to the service + `RunTask` (migrate family, cluster-conditioned) + `DescribeTasks` (cluster tasks); `iam:PassRole` ONLY the exec+task roles (condition `iam:PassedToService=ecs-tasks.amazonaws.com`); CloudWatch Logs read on the backend+migrate groups. **No admin, no Secrets Manager write.**
  - Output `gha_deploy_role_arn`.
- `terraform fmt`/`validate` clean; `terraform plan` = **3 to add, 0 to change, 0 to destroy** (OIDC provider + role + role policy; **no destroys**).
- **Applied — 3 added, 0 changed, 0 destroyed** (`terraform plan` after = "No changes").
  - **`gha_deploy_role_arn = arn:aws:iam::412058343855:role/sps-shared-dev-gha-deploy`**
  - OIDC provider + least-privilege deploy role live; trust scoped to `repo:sps-tech-dev/sps-staffing:ref:refs/heads/develop`.
- (Stage 4 = the GitHub Actions workflow that assumes this role on pushes to `develop`.)
- **Status:** ✅ Applied.

### CI/CD dev pipeline — `.github/workflows/deploy-dev.yml` (written, not yet tested) 🟡
- Wrote the dev deploy workflow (repo root `.github/workflows/`). Trigger: push to `develop` + `workflow_dispatch`. Permissions `id-token: write` + `contents: read`. Concurrency: per-branch, queue (no cancel).
- Steps: checkout → OIDC creds (`sps-shared-dev-gha-deploy`, no stored keys) → ECR login → **buildx ARM64** image (QEMU cross-build), tags `${sha}` + `develop-latest`, push → **register backend + migrate task-def revisions by fetch-and-modify of the LIVE task defs** (swap image only — preserves ARM64 runtime_platform, env, Secrets Manager `secrets`, exec/task roles, log config; zero drift, no hardcoded secrets) → **run migrate task FIRST** (`alembic upgrade head`, expand/contract — reuses the service's own network config so no `ec2:Describe*` needed; checks exit 0, tails CloudWatch; service NOT updated if it fails) → **then** `update-service` + `wait services-stable` (fails loudly) → health-check `/healthz` + `/readyz` (db:ok/redis:ok).
- Migration policy: dev = automatic; **UAT/prod gated migrations stubbed as a commented extension point** (GitHub `environment:` + required reviewers), not implemented (those envs don't exist).
- **Validated with `actionlint` (docker) — clean, exit 0**; YAML parses (1 job, 11 steps).
- Committed to `develop` (`ea7a52d`); push triggered the first run.
- **First run GREEN** ✅ — run ID **28258336432** (`https://github.com/sps-tech-dev/sps-staffing/actions/runs/28258336432`). All steps passed: keyless OIDC auth (`sps-shared-dev-gha-deploy`), ARM64 buildx build + ECR push, fetch-and-modify task-def registration, **expand/contract migrate-before-deploy** (`alembic upgrade head` ran first — idempotent no-op, exit 0 — then service rolled + `wait services-stable`), and `/healthz` + `/readyz` health check.
- **Status:** ✅ Tested — dev CI/CD pipeline live and green on push to `develop`.

### Slice 0 — frontend scaffold landed (applied) ✅
- Copied the F0 web-starter → `frontend/` (Next 15 · React 19 · TS · Tailwind v4 · TanStack Query): brand tokens, responsive AppShell, UI kit, typed API client, role middleware, feature flags, candidate/employer demo dashboards (mock data). Rejected the `spstechnosoft-platform` skeleton.
- **Security:** Next 15.1.6 → **15.5.19**, React → **19.2.7** (cleared critical/high CVEs). `npm audit`: 0 critical / 0 high; 3 moderate remain (postcss build-time; **next-intl** — bump to v4 tracked for the i18n slice).
- Flat ESLint config added; fixed 3 lint findings (`LucideIcon` type; 2 unused imports). **typecheck + lint exit 0**; `npm run dev` boots; `/` + `/candidate` + `/employer` render 200 (portal routes gated by role middleware via `sps_session` cookie).
- Package manager: **npm** (lockfile committed). Committed `13d8768` to `develop` (frontend only — no frontend deploy target in the pipeline yet; the push triggers an idempotent backend deploy run).
- **Status:** ✅ Slice 0 done — scaffold version-controlled and runnable.

### Slice 1 — Auth + tenancy spine (applied) ✅
- **Backend** (`/api/auth/login,refresh,logout,me`): argon2 verify, HS256 JWT in httpOnly cookies (SameSite=Lax, host-only, Secure env-driven), Part 31 error envelope. **Tenant isolation: `tenant_id` from the verified JWT is authoritative**; `TenantScopedRepo.base_query` filters every read by it; `get_current_context` builds context from the token (BU from path/X-BU validated vs memberships). Shared validation (`app/validation.py`: email, 10-digit IN phone, PAN, name, password, pincode).
- **Frontend**: `/login` (native form — Enter submits, Tab navigates, email autofocus) → posts via the same-origin Next proxy; role read from the JWT cookie in middleware (replaced `sps_session`); zod validators mirror the backend; minimal `/admin/dashboard` landing.
- **Local loop** (`docker-compose.yml`: Postgres+Redis+backend, seeded via migrations 0001-0003 + founder password set locally): full integrated test green —
  - bad email → **422**; bad creds → **401**; founder login → **200** + access/refresh cookies + role `admin` + home `/admin/dashboard`; `/me` → identity (tenant SPS001, 3 BUs owner); `/me` no cookie → **401**; refresh → **200**; logout → **200**.
  - Proxy: login through Next → cookies bind to `localhost:3000`; `/admin/dashboard` allowed with cookie, **307 → /login** without.
- **Tests: 34 pass** incl. the **cross-tenant leakage test** (tenant A context cannot read tenant B's users, and vice-versa) — the isolation proof — plus validation units and auth integration. `typecheck` + `lint` clean.
- **Deployed to dev** (pipeline run `28279088830` GREEN) and smoke-tested: `/healthz`+`/readyz` ok, `/api/auth` failure paths return the correct envelopes. (Founder on dev RDS is still `invited`, so successful dev login awaits the JWT-secret wiring below.)
- **Status:** ✅ Slice 1 done (local + deployed + tested).

#### ⚠️ TRACKED must-do before enabling REAL login on dev (STOP-4 — new paid secret + IAM)
- Move `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` into Secrets Manager + wire the ECS task-def `secrets` block + execution-role read (currently dev would use config defaults), and set `COOKIE_SECURE=true` on dev (HTTPS). Then activate a dev login user. Not done now — it creates a paid Secrets Manager secret + modifies IAM (STOP-4); awaiting approval. No tokens are minted on dev until then (founder is `invited`), so defaults are unexercised.

### Slice 2 — Candidate dashboard on a real read-model (applied) ✅
- **Backend:** `GET /api/me/overview` — authenticated + tenant/user-scoped (via `TenantScopedRepo`), returns the candidate's real overview. Counts are 0 / `recent` empty until staffing tables land (Slice 3); `profileComplete` derived from the user's real fields. `app/readmodels.py` + `app/routers/me.py`.
- **Frontend:** candidate dashboard now consumes the real endpoint (mock fallback removed); added **loading / empty ("No applications yet") / error+retry** states.
- **Local loop verified:** candidate user (role `candidate`) login → `/candidate`; `/me/overview` → `{applications:0,interviews:0,offers:0,profileComplete:100,recent:[]}` (real, scoped); 401 without auth; page renders through the Next proxy.
- **Tests: 36 pass** (+ read-model auth/shape tests; isolation suite still green). typecheck + lint clean.
- **Deployed to dev** (pipeline `28284446348` GREEN); smoke: `/api/me/overview` → 401 unauth, `/healthz` ok.
- **Status:** ✅ Slice 2 done (local + deployed + tested).

### Slice 3 — Staffing core (applied) ✅
- **Migration 0004** (`staffing` schema): `clients`, `jobs`, `candidates`, `applications`. **Candidates tenant-scoped** (talent pool, no `business_unit_id`); clients/jobs/applications two-axis. Soft-delete, in-schema FKs, composite + GIN indexes, applications stage CHECK, `UNIQUE(job_id,candidate_id)`. `env.py` `include_schemas=True` so autogenerate sees non-default schemas. STOP-1 DDL approved; applied to dev RDS via the pipeline migrate step.
- **Backend endpoints** (auth + tenant/STAFFING scoped, staff-role gated, Idempotency-Key honored): clients/candidates/jobs create+list; applications create + stage PATCH (Part 5 state machine → 409 on illegal transition); `GET /jobs/{id}/pipeline`; `GET /client-portal/overview` real read-model. Candidate fields validated (email/phone/PAN). `pan` plaintext — PII encryption tracked hard-blocker before registration.
- **Frontend** (employer, role `client`): dashboard on the real overview; new Jobs (list+create) and Pipeline (applications-by-stage, read view) screens. Kanban drag-drop deferred to Slice 4.
- **Tests: 40 pass** (+ cross-tenant **job** isolation, illegal-transition 409, candidate-role 403, create/list). typecheck + lint clean.
- **Deployed** (pipeline `28285382909` GREEN). dev RDS verified: staffing tables present, `alembic=0004_staffing_core`, candidates has no business_unit_id; `/api/jobs` → 401 unauth, `/healthz` ok.
- **Status:** ✅ Slice 3 done (local + deployed + RDS-verified).

### Slice 4 — Employer kanban (drag-drop pipeline) (done) ✅
- Pipeline page → **@dnd-kit kanban**: drag a candidate card between stage columns; **optimistic** board move via `useChangeStage` (cache move + rollback), reverts on server **409 illegal transition** with an inline message, reconciles on settle. PointerSensor + **KeyboardSensor** (accessible). Responsive (scroll-x columns on mobile, 7-col on xl). Wired to existing `PATCH /applications/{id}/stage`.
- **No backend change.** typecheck + lint clean; **prod build compiles** the kanban (10 static pages).
- CI: added `frontend/**` to `paths-ignore` — frontend has no deploy target yet, so frontend-only commits no longer trigger backend redeploys. (This commit touched the workflow → ran pipeline `28285804972` GREEN, a backend no-op redeploy.)
- **Note:** the frontend is **not deployed anywhere** (no frontend hosting yet — CloudFront/ACM is future STOP-4 infra); Slice 4 is verified locally (build + endpoint tests). Deferred-dev-frontend remains tracked.
- **Status:** ✅ Slice 4 done (committed `0b147f0`; frontend verified locally).

### Slice 5 — Recruiter SLA hub (applied) ✅
- **Backend:** `GET /api/employee/overview` — auth, tenant + STAFFING scoped, staff-role gated. Active-stage application queue (oldest-first) with per-item **SLA** (ok/warning/breached vs a 24h target from time since last stage change) + open/breaching/breached counts.
- **Frontend:** `(portal)/employee` SLA hub — KPI strip + requisition queue (stage pill, age, SLA chip); loading/empty/error states; responsive.
- **Tests: 42 pass** (+ staff-only 403, queue+SLA shape). typecheck/lint/build clean.
- **Deployed** (pipeline `28286123358` GREEN); `/api/employee/overview` → 401 unauth, `/healthz` ok.
- **Status:** ✅ Slice 5 done (backend deployed + RDS-live; frontend verified locally).

### Slice 6 — Admin console (applied) ✅
- **Backend:** `/api/admin/{candidates,clients,jobs,audit-logs}` — paginated, tenant-scoped, **ADMIN-gated** (owner/super_admin/admin; stricter than the staff gate). Candidate `phone` **masked** in list view (`•••••1234`). Audit trail via `write_audit()` on `job.create` / `application.create` / `application.stage_change` (written inside the mutation tx). **Append-only is convention-only** — the restricted INSERT-only DB role remains a tracked pending item (NOT DB-enforced yet).
- **Frontend:** `@tanstack/react-table` generic `AdminTable` (sortable, responsive overflow, paginated, loading/empty/error) → `(admin)/admin/{candidates(search),clients,jobs,audit-logs}` pages, role `admin`.
- **PII:** admin console is **read-only for candidates** (no create/edit), so no PII write here — the PII-encryption hard blocker fires at the **candidate-registration** slice, not Slice 6.
- **Tests: 44 pass** (+ admin-only 403, paginated shape, audit trail populated for the 3 actions). typecheck/lint/prod build clean.
- **Deployed** (pipeline `28292962248` GREEN; no new migration — 0004 already live); `/api/admin/{audit-logs,jobs}` → 401 unauth, `/healthz` ok.
- **Status:** ✅ Slice 6 done (committed `617c030`; backend deployed + RDS-live; frontend verified locally).

### F5 — Marketing site + i18n (next-intl@4 bump) ✅
- **Security bump (mandatory):** `next-intl 3.26 → 4.13.0` — clears **both** prior advisories (open-redirect `<4.9.1`; prototype-pollution via `experimental.messages.precompile`). Also bumped direct `postcss → 8.5.15`. Remaining 2 moderate audit findings are **Next's vendored postcss** (latest Next 15.5.19; only "fixable" by a next@9 downgrade) — accepted/documented (build-time CSS, no attacker input).
- **i18n:** next-intl@4 **without locale routing** — `NEXT_LOCALE` cookie (`en` default, `hi`) resolved in `i18n/request.ts`; **scoped to the `(marketing)` route group** (own `layout.tsx` + `NextIntlClientProvider`); portal/admin untouched. `messages/{en,hi}.json`. `lang={locale}` on the marketing wrapper. See DECISIONS for the routing-vs-cookie fork (SSG-per-locale deferred → marketing renders `ƒ` dynamic, all app pages stay static).
- **Marketing site:** expanded `(marketing)/page.tsx` into a real landing page (hero, services/verticals trio, stats, CTA) + nav with **LocaleSwitcher** (client; sets cookie + `router.refresh()`) + footer — all translated. Responsive.
- **Tooling:** `next lint` → `eslint .` (flat config; `next lint` removed in Next 16). Fixed a pre-existing unused-import lint warning in `middleware.ts`.
- **Verified locally:** typecheck/lint/build clean; runtime smoke (`next start`) confirms `/` renders **en** by default and **hi** under `NEXT_LOCALE=hi` cookie. Frontend still not deployed (no hosting — STOP-4); frontend-only commit skips the backend pipeline (`paths-ignore`).
- **Status:** ✅ F5 done (frontend verified locally).

### F6 — AI feature flags + DPDP self-service (applied) ✅
- **Feature flags** (`app/features.py`): non-GA features OFF by default; `require_feature("ai")` → **404 when off** (probe-proof, not 403). `FEATURE_AI` env flag (default false). `GET /api/me/features` exposes resolved flags to the client.
- **AI** (`/api/ai/candidate-summary/{id}`): flag-gated, tenant-scoped, **deterministic stub** (no model call yet). Frontend `AiInsightsCard` self-gates (renders nothing when off) — mounted on the employer pipeline.
- **DPDP self-service** (`/api/privacy/*`): consent ledger (append-only `GET`/`POST /consent`), `POST /export` (account + linked candidates + applications bundle; records request), `POST /erase` (**records a `pending` request only — no deletion executed**), `GET /requests`. Idempotency-Key + audit on writes. Frontend `/privacy-rights` page (consent toggles, JSON export download, erasure-with-confirm, history).
- **Migration `0005`** (`shared.consents` + `shared.dpdp_requests`; CHECKs, FKs, indexes) — **STOP-1 honored**: DDL shown + approved before RDS apply. Local up→down→up + idempotency clean.
- **STOP-3 honored:** consent notices stubbed `[LEGAL COPY TBD]` + draft banner; `policy_version='2026-06-stub'`. No legal prose invented.
- **PII blocker:** Slices 6 & F6 added **no** candidate PII-write path (admin GET-only/masked; F6 writes only consent/dpdp rows; export omits phone/pan). The pre-existing staffing `POST /api/candidates` plaintext-PII path is unchanged and the encryption blocker remains OPEN/tracked.
- **Tests: 52 pass** (44 + feature-gate 404/200/auth + DPDP consent/export/erasure). typecheck/lint/build clean. Runtime smoke: all new routes 401 unauth.
- **Status:** ✅ F6 done (backend deployed + RDS-live; frontend verified locally).

### PII encryption — deploy 1: expand + backfill + cutover (Part 10) ✅
- **STOP-2 design** chosen with the user: app-layer **envelope encryption** (AES-256-GCM, DEK from KMS CMK `alias/sps-pii-dev`) for **PAN + phone**; **deterministic blind index** (`*_bidx` = HMAC-SHA256, separate Secrets Manager key) for dedup/exact-match; **email stays CITEXT**. See DECISIONS.
- **App:** `app/crypto.py` (envelope encrypt/decrypt, blind_index, `EncryptedStr` TypeDecorator). Candidate `phone_enc`/`pan_enc` are **`deferred`** (lists/queues never bulk-decrypt; decryption = explicit privileged access). `POST /api/candidates` now writes ciphertext + bidx and 409s on duplicate (Part 19); admin list masks via `*_bidx` presence (no decrypt).
- **Migrations:** `0006` expand (add `*_enc`/`*_bidx`), `0007` backfill + dedup uniques. Local up→down→up + idempotency clean; ciphertext verified plaintext-free; **57 tests pass** (+ crypto round-trip, ciphertext-at-rest, dedup 409, masked admin list).
- **Infra (STOP-4, applied):** `Project/pii.tf` — KMS CMK (rotation on) + `alias/sps-pii-dev`, `sps-shared-dev-pii-index-key` secret, IAM (task: GenerateDataKey+Decrypt on the CMK + GetSecretValue on the index secret; execution: GetSecretValue). Backend + migrate task defs wired `PII_KMS_KEY_ID` + `PII_INDEX_KEY`. `terraform apply` ran BEFORE the push (CI fetches the live task def). STOP-1 DDL shown + approved.
- **Key mode:** KMS in the deployed app/migrate tasks; LOCAL fixed-key for the local loop/tests (no AWS).
- **Deploy 1 LIVE-VERIFIED on dev RDS + dev KMS** (one-off Fargate probe via the migrate task def, since deployed-dev has no login): ciphertext-at-rest (KMS envelope) ✓, decrypt round-trip (KMS Decrypt) ✓, dedup blind-index unique 409 ✓, admin mask ✓, probe row cleaned up.
- **Status:** ✅ deploy 1 — app layer encrypted + live-verified; plaintext columns retained until contract.

### PII encryption — deploy 2: contract (drop plaintext) ✅
- `0008` drops legacy `staffing.candidates.phone` / `pan`. Model plaintext mappings + the test_pii plaintext assertion removed. Local up→down→up clean; **57 tests pass** on the contracted schema. STOP-1 DDL (2× DROP COLUMN) shown + approved; gated on deploy-1 live verification.
- Prod note (documented in the migration): a live-traffic contract needs an intermediate "unmap" deploy first; dev has no candidate traffic so the rollover window is a non-issue.
- **Status:** ✅ deploy 2 — plaintext PII columns removed; PII now exists only as KMS-encrypted ciphertext + HMAC blind indexes.

### Candidate registration — secure intake (applied, RDS-live) ✅
- **Public `POST /api/register/candidate`** (unauthenticated; tenant from Host): hCaptcha gate → DPDP consent gate (no PAN without consent) → tenant resolve → candidate persisted **encrypted** (`EncryptedStr` + blind index, dedup → 409) → consent recorded in the F6 ledger against the candidate. `GET /api/register/config` exposes sitekey + stubbed notices.
- **Migration 0009** (STOP-1 approved, applied to RDS): `consents.subject_user_id` → nullable + `subject_candidate_id` (soft ref) + CHECK exactly-one-subject. Local up→down→up clean.
- **hCaptcha = STOP-4** (real keys need an account; local/dev test mode passes a present token, missing → 400). **Consent copy = STOP-3** (`[LEGAL COPY TBD]`; cannot take real candidates until real wording).
- **Frontend `/register`:** multi-step RHF+zod wizard (keyboard Tab/Enter convention), hCaptcha widget, consent checkboxes. typecheck/lint/build clean; 0 new high/critical deps.
- **Host-resolution fix:** infra/env API hosts (`dev-api`/`staging-api`/…) added to `RESERVED_SUBDOMAINS` so the deployed single-tenant API resolves to the owner tenant (registration 404'd on `dev-api.*` before the fix).
- **Tests: 63 pass** (+ captcha gate, consent-required, encrypted-persist+consent-ledger, dedup-409, config, dev-api-host→owner).
- **LIVE-VERIFIED on dev RDS + KMS** over real HTTP: valid → 200 registered (encrypted write via KMS), duplicate phone → 409 (blind-index dedup), gates 400/422; probe rows cleaned up.
- **Status:** ✅ deployed + RDS-live + live-verified. Real signups blocked until STOP-3 (consent wording) + STOP-4 (hCaptcha keys) are resolved.

### Append-only enforcement — least-privilege app DB role (applied, RDS-live) ✅
- **What:** backend now connects as **`sps_app`** (non-owner) — full DML on business tables, only SELECT/INSERT on `shared.audit_logs` + `shared.consents` → **append-only is DB-enforced**, not convention. Migrate task stays on **master** (DDL); tests/maintenance use master too.
- **Infra (`Project/appdb.tf`, STOP-4 approved):** `random_password` + Secrets Manager `sps-shared-dev-app-db`; exec role injects `DB_USER`/`DB_PASSWORD` into the backend task def; task role reads it for bootstrap. Role+grants provisioned by an idempotent one-off ECS bootstrap (`backend/scripts/bootstrap_app_role.py`).
- **Staged apply (no image regression):** secret+IAM (`-target`) → bootstrap role → full apply with `-var backend_image_tag=<live SHA>` switching backend→`sps_app`. Grant model verified locally first.
- **LIVE-VERIFIED on dev RDS:** service stable; `/readyz` db:ok; **real registration → 200** (INSERT candidate+consent+audit as `sps_app`, the e2e check a probe alone could miss); dedup 409; a probe confirms **UPDATE/DELETE denied** on both ledgers. Probe row cleaned up.
- **Rollback path (confirmed clean):** repoint backend service to the prior task-def revision (`:23`, master).
- **Status:** ✅ deployed + RDS-live + live-verified. (New landmine logged in PENDING C3: `terraform apply` must pin `-var backend_image_tag` or it regresses the image.)

### DPDP export PII completion — privileged self-export decryption ✅
- **What:** `POST /api/privacy/export` now includes the principal's **own decrypted PAN/phone** (`_export_bundle` undefers + decrypts `*_enc` for candidates matched by tenant+email).
- **Scope/isolation:** only the authenticated principal's own records; test asserts A's export contains A's PII and **zero** of B's (isolation with decryption in the path).
- **Privileged + audited:** writes an `audit_logs` `dpdp.export` entry (`actor_id` = who, `ts` = when, `after.pii_disclosed=true`). Audit INSERT goes through `sps_app` (confirmed it can INSERT audit_logs).
- **No PII in Redis:** export is **no longer idempotency-cached** (caching the decrypted bundle would write PII to Redis) — each export is a separately-audited disclosure.
- **Masking unchanged:** admin/other views still mask via `*_bidx` presence; only self-export decrypts.
- **Read/decrypt only:** no new migration/grant. **64 tests pass** (+ decrypted-PII export + audit, A/B isolation).
- **Status:** ✅ built + locally verified; deploying + dev smoke (export path under `sps_app` via one-off task, since dev has no login).

### DPDP erasure engine — Stage 1 (disable + anonymize + audit + approval gate) ✅
- **Model (ratified, DECISIONS):** hybrid — disable-on-request → approval-gate → anonymize → retain de-identified records → (LATER) auto-purge. Stage 1 = everything except auto-purge.
- **Flow:** `POST /api/privacy/erase` soft-deletes the principal's candidates immediately (instant access loss), then legal-hold → exempt (manual approval) else auto-approve → **anonymize** (full_name→[erased], email/phone_enc/pan_enc null, **phone_bidx/pan_bidx cleared**, search_doc/source/resume_s3_key null; user disabled+anonymized) → append-only `dpdp.erasure_executed` audit → request `completed`.
- **Admin manual gate:** `/api/admin/erasure-requests` list + `/approve` /`/reject` /`/legal-hold` (admin-gated). `run_erasure` asserts the `approved` transition.
- **Retain (untouched):** consents, audit_logs (append-only — sps_app can't delete), dpdp_requests; applications de-identified transitively. S3 resume delete wired but inert (no keys yet; C5).
- **Auto-purge:** INERT STUB (`auto_purge_due_requests`) — reads `dpdp_retention_days` (None), deletes nothing; activation gated on legal Q1/Q3/Q5/Q6/Q7 (PENDING B1).
- **Migration 0010:** `dpdp_requests.legal_hold` + expanded status CHECK. Local up→down→up clean. STOP-1 DDL shown + approved.
- **Runs as `sps_app`** (UPDATE candidates/users + INSERT audit; never UPDATE/DELETE append-only).
- **Tests: 69 pass** (anonymize + blind-index clearing, retention, audit, legal-hold gate, approved-gate, purge no-op).
- **Status:** ✅ built + locally verified; applying 0010 + deploying.

### Staffing — Submissions (submit to client + feedback + status) ✅
- **Backend:** `staffing.submissions` (two-axis, FK→applications, status CHECK submitted/under_review/shortlisted/rejected, client_feedback, submitted_by). Endpoints (staff-gated, idempotent, audited): `POST /api/applications/{id}/submissions`, `GET /api/applications/{id}/submissions`, `GET /api/submissions` (dashboard w/ candidate+job), `PATCH /api/submissions/{id}` (feedback/status). Migration `0011` (STOP-1 DDL approved). New router `app/routers/workflow.py`.
- **Frontend:** `/employer/submissions` (list + inline status/feedback) + "Submit to client" action on pipeline cards + nav item. Responsive, loading/empty/error.
- **Tests: 72 pass** (+ submit/feedback/dashboard, bad-status 422, staff-gate 403). Migration up/down/up clean.
- **Status:** ✅ applied + deployed.

### Staffing — Offers (CTC, joining date, RTR / acceptance) ✅
- **Backend:** `staffing.offers` (two-axis, FK→applications, ctc, joining_date, status CHECK draft/released/accepted/declined/withdrawn, rtr_signed_at, accepted_at). Endpoints (staff-gated, idempotent, audited): `POST /api/applications/{id}/offers`, `GET /api/applications/{id}/offers`, `GET /api/offers` (dashboard), `PATCH /api/offers/{id}` (status/CTC/joining/RTR/acceptance — sets accepted_at on accept, rtr_signed_at on RTR). Migration `0012` (STOP-1 DDL approved).
- **Frontend:** `/employer/offers` (CTC+joining inputs, status, mark-RTR, accept) + "Offer" action on pipeline cards + nav item.
- **Tests: 75 pass** (+ create/RTR/acceptance/dashboard, bad-status 422, staff-gate). Migration up/down/up clean.
- **Status:** ✅ applied + deployed.

### Staffing — Interview scheduling ✅
- **Backend:** `staffing.interviews` (two-axis, FK→applications, scheduled_at, mode CHECK phone/video/onsite, status CHECK scheduled/completed/cancelled/no_show, interviewer_name, feedback). Endpoints (staff-gated, idempotent, audited): `POST /api/applications/{id}/interviews`, `GET /api/applications/{id}/interviews`, `GET /api/interviews` (dashboard soonest-first), `PATCH /api/interviews/{id}` (reschedule/mode/status/interviewer/feedback). Migration `0013` (STOP-1 DDL approved).
- **Frontend:** `/employer/interviews` (datetime, mode, status, feedback) + "Interview" action on pipeline cards + nav item.
- **Tests: 78 pass** (+ schedule/outcome/dashboard, bad mode/status 422, staff-gate). Migration up/down/up clean.
- **Status:** ✅ applied + deployed.

### Staffing — Invoicing (structure only; configurable/stubbed tax) ✅
- **Backend:** `staffing.invoices` (two-axis, FK→applications [placement] + clients). **15% placement fee computed** (`fee_percent` default 15 = SPS business term, configurable). **GST/TDS NOT hardcoded** — `gst_percent`/`tds_percent` NULL by default; tax computed ONLY when a rate is explicitly supplied (legal Q1). `base_amount`, `fee_amount`, `gst_amount`, `tds_amount`, `total_amount`, currency, status CHECK draft/issued/paid/cancelled. Endpoints (staff-gated, idempotent, audited): `POST /api/invoices`, `GET /api/invoices` (dashboard), `PATCH /api/invoices/{id}` (status + supply GST/TDS → recompute). Migration `0014`.
- **Frontend:** `/employer/invoices` (fee/total view, GST/TDS rate inputs with a "rates await legal" banner, status) + "Generate invoice" on accepted offers + nav item.
- **DDL (additive, two-axis, FK applications+clients):** see migration 0014. `fee_percent NUMERIC DEFAULT 15`; gst/tds percent+amount NULLable.
- **Tests: 81 pass** (+ 15% fee, no-tax-until-supplied, GST/TDS recompute, custom fee%, staff-gate). Migration up/down/up clean.
- **PENDING B5:** invoicing GST/TDS compliance specifics (rates, rounding, place-of-supply/RCM, HSN/SAC, numbering, PDF) await legal.
- **Status:** ✅ applied + deployed (tax inert until legal-confirmed rates).

### Staffing — Vendor / sub-vendor management (core) ✅
- **Backend:** `staffing.vendors` (name, contact_email/phone [business contact], commission_percent, status CHECK active/inactive) + `staffing.vendor_submissions` (vendor↔candidate attribution, optional job, status CHECK submitted/shortlisted/rejected/placed, notes). Both two-axis. Endpoints (staff-gated, idempotent, audited): `POST/GET /api/vendors`, `PATCH /api/vendors/{id}`, `POST /api/vendors/{id}/submissions`, `GET /api/vendor-submissions`, `PATCH /api/vendor-submissions/{id}`. Migration `0015` (two tables).
- **Frontend:** `/employer/vendors` (add-vendor form, vendor list w/ commission+activate, vendor-submissions attribution list w/ status) + nav item.
- **Follow-up (PENDING D3):** vendor_contracts / vendor_commissions / vendor_performance + vendor-submission create UI.
- **Tests: 84 pass** (+ vendor CRUD + submission attribution + status, bad-status 422, staff-gate). Migration up/down/up clean.
- **Status:** ✅ applied + deployed.

### Staffing — Final integration pass (E2E on dev) ✅
- **Full chain verified on dev RDS under `sps_app`** (via a one-off task calling the endpoint functions directly — the prod image has no httpx for TestClient): client → job → candidate → application → submission → offer(accepted) → interview → invoice (15% fee, GST/TDS inert) → vendor → vendor_submission; **all 5 workflow dashboards join** (candidate/job/client names). Probe artifacts cleaned up.
- **Tenant scoping:** every workflow query filters by `tenant_id` (+ `business_unit_id` two-axis); staff-gated; idempotent writes; canonical error envelope.
- **Full test suite: 84 pass**, incl. the **cross-tenant leakage** test (tenant A context cannot read tenant B).
- **Dev endpoints live + auth-gated** (401 unauth): `/api/{submissions,offers,interviews,invoices,vendors,vendor-submissions}`. `/readyz` db:ok.
- **Status:** ✅ staffing vertical workflow complete end-to-end on dev.

### Client Portal — Task 1: isolation foundation + leakage GATE ✅
- **Identity:** new `shared.client_users` (user_id, tenant_id, client_id soft-ref, status CHECK pending/active/rejected/suspended, UNIQUE(tenant_id,user_id)) — binds a login to one client; approval = status active + client_id bound (pending grants nothing). Justified vs memberships.client_id in DECISIONS.
- **Base-layer nested scoping:** `RequestContext.client_id` (from JWT); `TenantScopedRepo.base_query` nests `client_id` filter under tenant_id+BU when ctx.client_id set + model has client_id. `AuthQueries.active_client_binding` mints client_id into the JWT at login/refresh; deps reads it. Can't be forgotten per-endpoint.
- **Denormalized client_id** onto applications/submissions/offers/interviews (jobs+invoices already had it; backfilled from job) so the whole pipeline is base-scoped. Candidates stay tenant-scoped (pool not client-owned).
- **Migrations 0016 (client_users) + 0017 (pipeline client_id + backfill).** Local up→down→up + idempotency clean. DDL:
  - `0016`: CREATE TABLE shared.client_users(... client_id UUID, status CHECK(pending/active/rejected/suspended), FK tenant+user, UNIQUE(tenant_id,user_id)) + indexes.
  - `0017`: ADD COLUMN client_id + FK clients + index on applications/submissions/offers/interviews; UPDATE backfill from job→application chain.
- **THE GATE — `test_client_isolation.py` PASSES:** cross-client isolation on Job/Application/Submission/Offer/Interview (both directions), no cross-tenant read, staff not client-restricted, candidates only via scoped pipeline. **87 backend tests pass.**
- **Status:** ✅ foundation proven leak-free; safe to build the portal on top.

### Client Portal — Task 2: client self-registration (public, pending+unlinked) ✅
- **Backend:** `POST /api/register/client` (public; tenant from Host) → a PENDING, UNLINKED `shared.client_registration_requests` row. **Grants NOTHING** (no user, no client_users) until admin approval. Gates: hCaptcha (test-mode) → DPDP consent (422 if absent) → tenant resolve. Contact **phone encrypted** at rest (EncryptedStr + blind index; personal data); email CITEXT; consent + policy_version recorded. Audit `client.register`. Migration `0018` (revision id shortened to fit alembic_version varchar(32)).
- **DDL:** CREATE TABLE shared.client_registration_requests(company_name, industry, contact_person, email CITEXT, phone_enc/phone_bidx bytea, website, company_size, consent_data_processing, policy_version, status CHECK pending/approved/rejected, reviewed_by/at) + index(tenant_id,status).
- **Frontend:** `/register/client` RHF+zod form (company/industry/size, contact/email/phone, website, consent + hCaptcha) + success "pending review" screen + login link. Responsive, loading/empty/error.
- **STOP-3:** consent copy stubbed [LEGAL COPY TBD]. **STOP-4:** hCaptcha test-mode. (Both tracked launch-blockers.)
- **Tests: 91 pass** (+ captcha gate, consent-required, bad email/phone 422, pending+unlinked+encrypted, grants-nothing). Migration up/down/up clean.
- **Status:** ✅ applied + deployed.

## Pending / next steps

➡️ **The canonical, durable register of ALL outstanding/deferred items is
[`docs/PENDING.md`](PENDING.md)** — read it each session before assuming anything is
done. (This list is no longer maintained here to avoid two diverging copies.)

Infra already applied: security groups, RDS, Redis, ECS Fargate (backend live), ALB +
HTTPS/ACM (dev-api serves HTTPS).
