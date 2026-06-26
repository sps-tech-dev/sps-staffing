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

## Pending / next steps
- [ ] **DKIM CNAMEs** for Microsoft 365 (email migration not fully complete).
- [ ] **Backend lockfile migration** — switch to `use_lockfile = true`, then delete the `sps-staffing-tflock` DynamoDB table.
- [ ] **GST tax number** — add to AWS account tax settings.
- [ ] **audit_logs append-only enforcement** — create a restricted app DB role with INSERT-only grant on the audit tables (currently convention-only; structure is in place, grants deferred per decision B).
- [x] **Security groups** — alb / ecs / rds / redis. ✅ Applied.
- [x] **RDS** (PostgreSQL) in private-data subnets. ✅ Applied.
- [x] **Redis** (ElastiCache) in private-data subnets. ✅ Applied.
- [x] **ECS Fargate** services in private-app subnets. ✅ Applied (backend live).
- [x] **ALB** in public subnets. ✅ Applied (HTTP:80; HTTPS+ACM still pending).
