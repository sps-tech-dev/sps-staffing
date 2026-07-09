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

### Client Portal — Task 3: admin approval flow (the security gate) ✅
- **Backend (admin-gated):** `GET /api/admin/client-registrations` (pending-first queue, phone masked via bidx — no decrypt); `POST .../{id}/approve` (THE GATE — links to an existing or new clients row, creates the login `users` row [active, argon2 password admin-sets], creates an **ACTIVE `client_users` binding** [tenant_id+client_id], records consent, request→approved, audited `client.approve`); `POST .../{id}/reject` (audited `client.reject`). Idempotent. Only this explicit approval grants a client a scoped session.
- **Frontend:** `/admin/client-registrations` queue (company/contact/phone, set-initial-password + Approve&create-client / Reject) + nav item.
- **Tests: 94 pass** (+ approve links+activates+enables client login [asserts JWT carries client_id, role=client, home=/client], reject keeps no access, non-admin 403). No new migration.
- **Status:** ✅ applied + deployed.

### Client Portal — Tasks 4+5: client login/auth + transparency portal ✅
- **Task 4 (login + routing):** login mints `client_id` into the JWT from `active_client_binding` (role→`client`, home→`/client`). `deps` reads it; frontend middleware routes a bound client session to `/client` and **bounces it out of staff areas** (`/employer`,`/admin`). **Anti-leak hardening:** `_require_staff`/`_require_admin` + the employee hub now REJECT any session with `client_id` (a client can't reach the tenant-wide staff endpoints).
- **Task 5 (client portal, strictly client-scoped):** new `app/routers/client_portal.py` mounted at `/api/client/*`, gated by `_require_client` (client_id required), every read through `TenantScopedRepo.base_query` (auto client-scoped): `GET /overview` (KPIs + funnel), `/jobs`, `/pipeline` (by stage), `/submissions` (candidate + stage), `/interviews`, `/offers`. Writes: `POST /submissions/{id}/feedback` (approve→shortlist / reject; target must be in the client's scope or 404), `POST /jobs` (client_id forced from session → recruiter queue). Audited.
- **Frontend `/client/*`:** overview (KPIs/funnel/interviews/offers), submissions (approve/reject), jobs (list + post), pipeline (read board); `client` nav repointed to `/client`. Responsive, loading/empty/error.
- **Tests: 99 pass** — incl. `test_client_portal` (client sees only own jobs/candidates, feedback only on own submission [other→404], post-job owned by client, non-client 403) and the **staff-endpoint rejection** of a client session. No new migration.
- **Status:** ✅ applied + deployed.

### Client Portal — Task 6: final integration pass (E2E on dev) ✅
- **E2E on dev RDS (under sps_app):** client registration request → admin approve+link to a clients row → **active client_users binding** (login would mint client_id) → client context sees **ONLY its own** jobs/submissions/overview → **cross-client AND cross-tenant leakage = NONE** (re-checked via the base repo, both directions). Probe artifacts cleaned up (master).
- **Dev smoke:** `/api/client/{overview,jobs,submissions}` + `/api/admin/client-registrations` live + 401 unauth; `/api/register/client` no-consent → 422; `/readyz` ok.
- **Full backend suite: 99 pass** incl. all leakage tests (`test_client_isolation`, `test_client_portal`, staff-endpoint rejection, `test_tenant_isolation`).
- **Status:** ✅ client self-service portal complete + leak-proof end-to-end on dev.

### Client Portal — Task 7: client-internal roles (HR vs hiring manager) — owner-scoped jobs + HR-only offer-write ✅
Two **client-user roles** nested INSIDE the existing tenant+client isolation (a third scoping
level + an orthogonal permission gate). Set at user creation; carried in the JWT.
- **Role model (see DECISIONS 2026-06-28):** `client_admin` (HR) — sees ALL the client's jobs +
  full pipelines; the ONLY client role that can WRITE offers (release + joining date); invites
  teammates; reassigns jobs. `client_manager` (hiring manager) — sees the FULL pipeline of ONLY
  their OWN posted jobs (`owner_user_id = self`), no cross-manager visibility; offer card is
  READ-ONLY. The approved self-registrant is the client's first user → `client_admin`.
- **Two independent axes:** (a) **row scope** — `TenantScopedRepo.base_query` nests
  `owner_user_id = self` for a `client_manager` (no owner filter for HR), under tenant→BU→client;
  (b) **offer-write permission** — release / joining-date / team / reassign gated by
  `_require_client_admin` (reads `ctx.client_role` from the JWT); manager → 403 on write, 200 on read.
- **Backend:** `client_users.role` (CHECK `client_admin`/`client_manager`) carried into JWT via
  `active_client_binding` → `_build_claims` (`client_role` claim) → `ctx.client_role` (deps) →
  base_query + gate; `owner_user_id` denormalized onto jobs + applications/submissions/offers/
  interviews (set by every creator: client post-job = poster; create_application = job's owner;
  submission/offer/interview = application's owner). New `/api/client/*` endpoints (HR-only):
  `POST /offers/{id}/release` (draft→released + joining date), `PATCH /offers/{id}/joining-date`,
  `GET|POST /team` (roster + invite teammate w/ chosen role), `POST /jobs/{id}/reassign` (cascades
  owner onto the whole pipeline; new owner must be an active user of this client; audited). `/me`
  now returns `client_role`. `approve_client` stamps the first user `client_admin`.
- **Migration `0019_client_roles_owner`** (applied via the dev pipeline; local up/down/idempotent clean):
  - `ALTER TABLE shared.client_users ADD COLUMN role text NOT NULL DEFAULT 'client_admin';`
  - `ALTER TABLE shared.client_users ADD CONSTRAINT ck_client_users_role CHECK (role IN ('client_admin','client_manager'));`
  - for each of `staffing.{jobs,applications,submissions,offers,interviews}`:
    `ADD COLUMN owner_user_id uuid NULL;` + `CREATE INDEX ix_<t>_owner_user_id ON staffing.<t>(owner_user_id);`
  - backfill: `UPDATE staffing.applications a SET owner_user_id = j.owner_user_id FROM staffing.jobs j WHERE j.id = a.job_id;`
    then submissions/offers/interviews `SET owner_user_id = a.owner_user_id FROM staffing.applications a WHERE a.id = x.application_id;`
  - `owner_user_id` is a SOFT ref to `shared.users` (no cross-schema FK — same rule as `client_id`). Additive; reversible.
- **Frontend:** `/client/offers` (HR-editable card — release draft + set/adjust joining date; manager
  read-only), `/client/team` (HR: roster + invite teammate + per-job reassign; manager → "HR access
  only" notice), nav items Offers + Team. `useClientMe()` drives the role-conditioned UI. Responsive,
  loading/empty/error. tsc + eslint clean.
- **THE GATE — `tests/test_client_owner_scoping.py` (8 tests) PASSES before UI:** manager A sees only
  own pipeline / B invisible both directions; HR sees all; manager 403 offer-write + 200 read; HR
  releases → manager sees read-only; HR reassign works + cascades, manager 403; reassign→non-member
  422; team HR-only. Existing `test_client_isolation` (cross-client) + `test_tenant_isolation`
  (cross-tenant) STILL pass. **Full backend suite: 107 pass.**
- **E2E on dev RDS (2026-06-28, under `sps_app`):** `scripts/e2e_client_roles.py` via a one-off ECS
  Fargate task (backend task def rev 40, image `c1b6fad`) — **25/25 PASS, exitCode 0**: owner-scoping
  both ways (manager A↔B invisible), HR sees-all, offer-write gate (manager 403 / HR releases + sets
  joining date), released-offer read-only on the owning manager's job, reassign cascade (old owner loses
  it / new owner gains it), reassign→non-member 422, team HR-only, and cross-client + cross-tenant
  leakage = NONE; probe artifacts cleaned up. Migration `0019` applied by the pipeline (migrate exitCode 0);
  service stable; `/readyz` 200.
- **Status:** ✅ owner-scoped jobs + HR-only offer-write proven leak-free on dev; applied + deployed.

### Marketing — Corporate site + Staffing vertical landing (video hero + animations) ✅ (local only — NOT deployed)
The public spstechnosoft.com front door, rebuilt as a two-level marketing site. **Frontend-only; no
backend/auth/migrations touched. Built + run locally; deploy is a separate later step.**
- **Two levels:** **Level 1 — corporate site at `/`** (purely informational, **NO login anywhere**)
  presenting SPS Technosoft Pvt Ltd as a multi-vertical company. **Level 2 — staffing vertical at
  `/staffing-and-recruitment`** (reached from the Services "Staffing & Recruitment" card) which carries
  the **login entries** into the existing portals.
- **Video hero** (`components/marketing/video-hero.tsx`): full-viewport `<video autoPlay muted loop
  playsInline poster=…>` with BOTH `<source>` (webm + mp4) over the optimized assets in
  `public/video/` (NOT re-encoded). Dark gradient overlay (navy 55%→85%, deeper at bottom) + left wash
  for text readability. **Reduced-motion AND small screens (<768px) → poster only, no video** (perf +
  a11y), decided client-side via matchMedia. Poster served through `next/image` (priority).
- **Animations** (`components/marketing/reveal.tsx`, Framer Motion 12): scroll-triggered fade+slide-up
  reveals (`<Reveal>`) and staggered groups (`<RevealGroup>`/`<RevealItem>`), premium ease, **all
  gated by `useReducedMotion()`** → static when the user opts out. Header solidifies on scroll.
- **Routes built** (all under the `(marketing)` group, English-first copy written in-house):
  `/` (corporate home — video hero, intro, 3-vertical band, why-SPS, stats, CTA), `/about`,
  `/services` (3 vertical cards → staffing / academy / consulting, alternating visual panels),
  `/career` (employer brand + **empty "no open roles" state** + how-to-apply), `/contact`
  (**stub form — no email infra; validates + success state, sends nothing, marked TODO**),
  `/academy` + `/consulting` (**on-brand "Coming soon"** placeholders), and
  `/staffing-and-recruitment` (own video hero, AI-assisted-quality-hiring narrative, problems / how-it-
  works 5-step / why-SPS / placement-as-value, **three role logins → `/login?role=client|candidate|
  employee`** using the existing auth flow + **Post a Job → `/register/client`**).
- **Chrome:** new corporate `SiteHeader` (logo+name left, nav Home·About·Services·Career·Contact
  right, mobile hamburger, **no login**) + `SiteFooter` (company brief, nav, verticals, contact,
  copyright). The old 3-vertical `/` page was replaced (preserved in git history); next-intl provider
  retained so app locale plumbing is intact.
- **Brand:** Recruit Blue `#1B5FE8` / Navy `#0D1B3E` / Gold `#E8A020` / Sky `#5B8FFF`, Sora + DM Sans +
  DM Mono. Responsive 360/768/1024/1440; semantic headings, alt text, keyboard nav, focus states.
- **Quality:** `tsc` clean, `eslint` clean (marketing files 0 warnings; 2 pre-existing unrelated
  warnings in `lib/nav.ts`), `next build` ✓ (37/37 pages). `npm run dev` boots clean; all 8 marketing
  routes 200, video assets serve (mp4/webm/jpg), existing app routes/portals unaffected (login 200,
  guarded portals 307→login).
- **Stubbed / deferred:** contact form is a no-op preview (email infra pending — PENDING E1); `/academy`
  + `/consulting` are Coming-soon; careers shows an empty openings state. Added dep: `framer-motion`.
- **Status:** ✅ built + verified locally at `localhost:3000`. **NOT deployed** — deploy is the next
  separate step (frontend has no deploy target yet — see PENDING C1).

### Marketing — replaced with user-provided Figma design (light theme, multi-page) ✅ (local only — NOT deployed)
Per the user's direction ("make the site look like this + replace Stratum → SPSTechnosoft"), the
dark video-hero marketing site above was **superseded** by a faithful port of a Figma Make export
(`Create Home Page Content.zip`). Frontend-only; backend/auth/portals untouched.
- **Source:** Figma Make export (Vite + React, `motion/react`, lucide, **no shadcn components used** —
  plain Tailwind + inline hex). Ported into Next.js as one client module `app/(marketing)/_design/
  site.tsx` (exports `Navbar`, `Footer`, `FadeIn` + 8 page components), with thin server route pages
  re-exporting each (so per-page `metadata` works).
- **Conversion (scripted):** `react-router` → Next (`Link href`, `usePathname`, dropped
  `HashRouter`/`Routes`/`ScrollToTop`; `NavLink` → active-aware `Link`); `motion/react` →
  `framer-motion`; **all "Stratum" → "SPSTechnosoft"** (27 occurrences); fixed a latent design bug
  (`Smartphone` icon used but never imported); added `"use client"`. **Images + copy are used verbatim
  from the design** (17 Unsplash URLs, all section text).
- **Look:** light canvas `#F0F4FA`, navy `#0A1628` + accent blue `#1A56DB`, **Outfit** headings + **DM
  Sans** body (Google Fonts `@import` in `globals.css`). Fixed white navbar (solidifies on scroll,
  mobile hamburger), dark footer.
- **Routes (8):** `/` (home: gradient hero, stats, who-we-are, 3 verticals, clients, testimonials,
  values, CTA), `/services`, `/services/staffing`, `/services/education`, `/services/it`, `/about`
  (story + leadership), `/career` (roles + filter), `/contact` (**stub form — `setSubmitted(true)`, no
  backend**). Old video-hero pages (`/staffing-and-recruitment`, `/academy`, `/consulting`) + their
  components removed.
- **Note:** this design is a pure marketing site — **no login entry points** (the earlier staffing-page
  login buttons are not in this design). The app portals (`/login`, `/client`, `/employer`,
  `/register/client`, candidate) are **unchanged and still reachable directly**; wiring login back into
  the marketing chrome can be added on request.
- **Quality:** `tsc` clean · `eslint` clean (site.tsx uses a file-level disable for `no-img-element` +
  `no-unescaped-entities`, appropriate for ported design copy/imagery; 2 pre-existing unrelated
  warnings in `lib/nav.ts`) · `next build` ✓ (37/37). `npm run dev` → all 8 routes 200, branding =
  SPSTechnosoft (0 "Stratum"), existing app routes/portals intact (login 200, guarded portals 307).
  The hero video assets in `public/video/` remain in the repo (unused by this design).
- **Status:** ✅ ported + verified locally at `localhost:3000`. **NOT deployed.**

#### Marketing — round-2 fixes (local only) ✅
- **Real logo:** `public/sps-logo-horizontal-1920.png` (full lockup) in the header, `public/sps-logo-mark-512.png`
  (cube mark) in the footer; replaced the placeholder cube+wordmark. Brand reads **"SPSTechnosoft"** (one word) —
  removed the stray period after the wordmark in both header and footer.
- **Header:** removed the "Get in Touch" button; nav (Home · Services · Careers · Contact · About) is now right-aligned
  (logo left). Mobile hamburger menu also drops the CTA.
- **Login entries on `/services/staffing`:** new "Portal Access" band with three distinct buttons — **Client / Candidate /
  Employee Login** → `/login?role=client|candidate|employee` (existing auth → /client, candidate dashboard, /employer) —
  plus a **Post a Job** CTA → `/register/client`. Corporate pages stay login-free.
- **Home:** avg. placement time **12 → 30 days** (hero badge + the staffing-card claim + staffing stat, kept consistent);
  removed the hero "Explore Services" / "Talk to Us" buttons (closing CTA band unchanged); removed the broken/404 inset
  image in "Who We Are" (and its container); "Trusted by industry leaders" is now a continuous **right-to-left marquee**
  (CSS `@keyframes marquee` in globals.css, two copies for a seamless loop, pause-on-hover, reduced-motion → static).
- Verified: `tsc`/`eslint`/`next build` clean (37/37), all 8 routes + /login + /register/client = 200, portals
  (/client,/employer,/candidate) still 307→login. **NOT deployed.**

#### Marketing — round-3 fixes (local only) ✅
- **Header logo bigger + no tagline:** the supplied horizontal PNG had the "STAFFING · IT SERVICES · EDTECH"
  tagline baked in (and the cube spans full height, so a plain crop would clip it). Generated a clean
  tagline-free lockup `public/sps-logo-header.png` (PIL: erased the tagline band right-of-cube/below-wordmark,
  tight-cropped → 2192×446) and enlarged it in the header (`h-9` → `h-12`).
- **Marquee seamless:** replaced the flex `gap-6` on the track with a per-item `mr-6` so each of the two copies
  includes its trailing space — the copies now tile exactly at `translateX(-50%)`, removing the stutter/pause
  after the last logo. Constant, gap-free right-to-left flow.
- **Equal value cards:** "Built on Values That Last" cards now `h-full` (and the `FadeIn` grid item `h-full`),
  so all four are equal height regardless of text length (grid already equalizes width).
- **Consistent inner heroes:** added a shared `PageHero` that reuses the Home hero's exact blue treatment
  (gradient + radial glow + dot pattern + bottom fade) at `min-h-screen`; `/services`, `/about`, `/career`,
  `/contact` now use it (Career keeps its role-filter buttons via `children`).
- Verified: `tsc`/`eslint`/`next build` clean (37/37); all routes 200; portals still 307→login. **NOT deployed.**

#### Marketing — round-4 fixes: per-vertical color system + transparent header (local only) ✅
- **Header = footer-matched + transparent:** the header logo now matches the footer exactly (cube mark
  `sps-logo-mark-512.png` `w-9 h-9` + "SPSTechnosoft" `text-xl` wordmark, flex-centered → wordmark
  cleanly vertically aligned with the cube). The header background is **transparent over the hero**
  (white logo/nav) and **solidifies to navy (`#0A1628`/85 + blur) on scroll** — it now merges into the
  blue hero instead of sitting on a white bar. (Removed the now-unused combined `sps-logo-header.png`.)
- **Per-vertical color system tied to the logo's three cube faces** — applied to BOTH the vertical's
  card (Home "What We Deliver" + `/services`) AND its detail-page theme:
  - **Staffing → Blue `#1B5FE8`** (person/top face)
  - **EdTech & Academy → Gold `#E8A020`** (graduation-cap face; was green)
  - **IT Services & Consulting → Navy `#0D1B3E`** (code `<>` face; was purple)
  Each card uses its own face color (icon/accent/border/hover/Learn-More); each detail page's accents
  (badge, buttons, highlights, checks, CTAs) pick up its face color. Decorative multi-color sets (login
  role cards, hiring-engagement cards, IT service-portfolio icons) intentionally stay varied.
- **Vertical detail-page heroes** (`/services/staffing`, `/services/education`, `/services/it`) now use
  the **full `min-h-screen` hero treatment** (gradient + radial glow + dot pattern + bottom fade,
  matching the other inner pages) — **tinted per vertical**: staffing blue, education gold (warm-dark
  gradient + gold accents), IT deep-navy (with light/white accents so they read on the dark hero).
- Verified: `tsc`/`eslint`/`next build` clean (37/37); all routes 200; auth/portals untouched
  (307→login). **NOT deployed.**

#### Marketing — round-5 fixes: white header + image heroes on every page (local only) ✅
- **Header reverted to white:** solid white (`bg-white` scrolled / `bg-white/95` blur at top) with the
  **dark logo** (cube mark + navy "SPS" / blue "Technosoft") and **dark nav links** (active
  `#1B5FE8`/`#E8EFFE`), logo left, nav right. (Undid the transparent-over-hero version.)
- **Inner-page heroes now image + page-specific content:** generalized `PageHero` into the Home-hero
  2-column treatment (min-h-screen, gradient + glow + dots + bottom fade) with an optional **per-page
  image** (rounded, shadow, gradient scrim) + a **floating accent badge**, and page-specific badge +
  heading + intro copy:
  - `/about` — company-story intro + team image + "7+ Years" badge
  - `/services` — three-verticals intro + collaboration image + "3 Verticals" badge
  - `/career` — join-us intro + team image + "Intern → Hire" badge (role-filter buttons kept)
  - `/contact` — get-in-touch intro + office image + "< 4 hrs" response badge
- **Vertical detail heroes:** `/services/staffing` now uses an image + content hero (recruiter/candidate
  image + "30 Days" / "80K+" floating cards) consistent with Home and its blue theme; `/services/education`
  and `/services/it` already had image heroes (gold / navy themed) — unchanged. Per-vertical color
  theming preserved throughout.
- All hero images are verified-loading Unsplash URLs. `tsc`/`eslint`/`next build` clean (37/37); routes
  200; auth/portals untouched (307→login). **NOT deployed.**

#### Marketing — global widgets: scroll-to-top + chat (local only) ✅
- **Reference pattern:** `Reference/spstechnosoft-portal/` implements scroll-to-top as a **footer "Back to
  top" button** (`window.scrollTo({ top: 0, behavior: 'smooth' })`) plus a navbar `scrollY > 40`
  threshold for the solid-on-scroll header; it has **no chatbot** (grep found none). Adapted the
  scroll-to-top into a **floating FAB** (appears past `scrollY > 400`, re-skinned to our brand); built the
  chat widget fresh.
- **Component:** `components/marketing/site-widgets.tsx` (`<SiteWidgets/>`), rendered **only** from
  `app/(marketing)/layout.tsx` → shows on every public page (Home, About, Services, the 3 vertical detail
  pages, Career, Contact, staffing) and **never** on the app portals (`(portal)`), registration/login
  (`(auth)`), or admin (`(admin)`) — they're separate route groups.
  - **Scroll-to-top:** floating button bottom-right (`bottom-24`), appears after 400px, smooth-scrolls to
    top (`behavior:'auto'` when reduced-motion), `aria-label`, hidden while the chat panel is open so they
    never overlap.
  - **Chat widget:** brand-gradient FAB (`bottom-6`) → opens a panel (`role="dialog"`, Esc to close,
    `aria-expanded`) with a greeting, a short message form that **composes a `mailto:`** (FRONT-END ONLY —
    no AI/LLM/paid backend), and Email + WhatsApp quick links. Structured so a real backend can be added
    later. WhatsApp number is a placeholder.
- Verified: `tsc`/`eslint`/`next build` clean (37/37); chat present on all 8 marketing routes, absent on
  `/login`, `/register`, `/register/client`; portals still 307→login. **NOT deployed.**
- **Round-2 — replaced the contact widget with a RULE-BASED chat assistant** (still zero-cost, front-end
  only, no backend/API/LLM). Menu-driven: opens with a greeting + quick-reply **chips** (Our Services,
  Staffing, EdTech, IT, Careers, Contact, How to get started); each chip shows a **pre-written** answer
  (accurate to our 3 verticals — no invented services/prices) + a link button to the relevant page;
  "Our Services" **branches** into the 3 verticals; every branch offers "☰ Back to menu". Free-text input
  uses **simple keyword matching** (job/hire→staffing, course/training→edtech, software/cloud→IT, etc.)
  with a graceful fallback (re-show menu + contact link). Conversational UI (assistant/user bubbles,
  `aria-live`, `role="dialog"`, Esc, keyboard, reduced-motion). The **scroll-to-top button now shares the
  chat accent** (`#1B5FE8`). All copy is in a `TOPICS` map so a real backend can be added later. Lint/tsc/
  build clean (37/37); scoping unchanged (marketing only). **NOT deployed.**

#### Marketing — round-6 fixes: contact details, LinkedIn, footer spacing, staffing image (local only) ✅
- **Footer column spacing** tightened: the 4-col grid gap `gap-10` → `gap-x-6 gap-y-10` (closer columns,
  balanced; keeps vertical spacing for the mobile stack).
- **Contact details updated everywhere** (footer + `/contact` info panel + the contact-form phone
  placeholder + the chat widget's `EMAIL`): **email `info@spstechnosoft.com`**, **phone `+91-8920756557`**,
  **location `Vadodara, Gujarat` (serving clients globally)**. The About company line is now
  "Vadodara-based". (One `Bengaluru` remains only in a **sample job listing** on `/career` — demo data, not
  our contact info — left intentionally.)
- **LinkedIn** → `https://www.linkedin.com/company/spstechnosoft/` with `target="_blank"
  rel="noopener noreferrer"`: footer social icon (now an objects array; LinkedIn opens new-tab, the other
  social icons keep `#` placeholders + `aria-label`s) and the three About "Connect on LinkedIn" links.
- **Staffing image** — replaced the badly-cropped Unsplash photo with the user-provided
  `public/staffing-team.webp` ("Find the Right People" graphic) across all three uses (Home "What We
  Deliver" card, `/services` card, `/services/staffing` hero). On the short Home card the crop now uses
  `object-position: center 30%` (added a per-card `imgPos`) so the subject/graphic isn't cut off; the
  larger 16/10 and 4/3 containers keep it centered.
- Verified: `tsc`/`eslint`/`next build` clean (37/37); contact values live on home + contact; LinkedIn href
  + new-tab attrs present; `/staffing-team.webp` serves 200; routes 200; auth/portals untouched
  (307→login). **NOT deployed.**

## 2026-07-04 — B.1: Resume upload + text extraction + erasure S3 delete ✅ (deployed)

First task off `SPS_MASTER_BUILD_PLAN.md` Part B. Planned → built → **STOP-1 approved** →
deployed to dev → verified on real S3.

- **Migration `0020_candidate_resume`** (STOP-1 approved before RDS): adds `resume_text text NULL`
  + `resume_uploaded_at timestamptz NULL` to `staffing.candidates` (`resume_s3_key` existed since
  0004 with no writer). Additive/reversible, metadata-only DDL; local `up→down→up` + idempotency
  clean; applied to dev RDS by the pipeline (migrate-first, exit 0).
- **`app/storage.py` (new):** presigned-URL-only S3 access (DECISIONS 2026-06-26) — PUT/GET presign
  (300 s TTL, ContentType bound into the PUT signature), `head_object`/`get_object_bytes`/
  `delete_object`, canonical key builder `tenant=<t>/business_unit=STAFFING/candidates/<c>/<uuid>.<ext>`.
  boto3 client per call (moto/test friendly). Bucket never exposed; browsers never see AWS creds.
- **`app/resume_parse.py` (new):** pure-Python extraction — PDF via `pdfminer.six`, DOCX via
  `python-docx` (+`docx2txt` fallback), legacy `.doc` accepted but extracts empty (no pure-python
  extractor; logged). Output capped 200k chars, control chars stripped; parse failure never fails
  the upload. All deps pure-Python → ARM64 slim base builds clean.
- **`app/routers/resumes.py` (new, staff-gated, tenant-scoped):**
  - `POST /api/candidates/{id}/resume/presign` — validates content-type (pdf/doc/docx) + declared
    size ≤ 10 MB → presigned PUT + key under the candidate's canonical prefix.
  - `POST /api/candidates/{id}/resume/confirm` — **key must match this candidate's prefix**
    (`KEY_MISMATCH` otherwise: can't confirm someone else's object); `head_object` proves the PUT
    happened and re-checks the **real** size/type (presigned PUT can't bind size — violations are
    deleted + 422); server-side download → synchronous text extraction (persistence seam is
    worker-ready for B.10) → sets key/timestamp/text; `Idempotency-Key` + `write_audit`
    (`candidate.resume_upload`) inside the txn. Timeline event = **TODO(B.2)** hook only.
  - `GET /api/candidates/{id}/resume` — 300 s presigned GET; 404 when no resume.
- **Erasure (PENDING C5 closed):** `_delete_resume_objects` is now real (`storage.delete_object`;
  task role already had `s3:DeleteObject` — `Project/s3.tf`, verified not added); anonymize scrub
  additionally nulls `resume_text` (extracted text is PII) + `resume_uploaded_at`.
- **C5 config fix:** `settings.storage_bucket` now reads the **`S3_BUCKET`** env the task def
  actually injects (AliasChoices; previously only `STORAGE_BUCKET` was read → deployed code would
  have silently used a wrong default bucket name).
- **Tests: 107 → 118** (`tests/test_resumes.py`, S3 mocked with moto): presign 401/403/422-type/
  422-size; confirm sets key+timestamp+non-empty text (real PDF + DOCX fixtures); foreign-prefix
  confirm rejected; missing-object confirm rejected; GET 404→presigned URL; cross-tenant candidate
  404 (leak test); **erase deletes the S3 object + nulls all three columns**. Full suite green.
- **Deploy:** commits `2b6f59f..5ce38d5` (5 logical groups) → pipeline run `28697269339` green
  (migrate exit 0 → service stable → health check). Dev smoke: `/healthz` + `/readyz` ok; both new
  endpoints 401 unauthenticated on `dev-api`.
- **Real-S3 one-off verification (what moto can't prove):** `backend/scripts/verify_resume_s3.py`
  run as a one-off Fargate task on the **backend** task def (task role + injected `S3_BUCKET` +
  `sps_app` DB creds — the exact runtime path): probe candidate → presigned PUT (plain urllib, no
  SDK creds client-side) → head/size → server-side download + extraction → persist to the 0020
  columns on **dev RDS** → presigned GET byte-match → erasure-style delete (object gone, columns
  nulled) → self-cleanup. **PASS, exit 0.** Bucket resolved to
  `sps-shared-dev-storage-412058343855` from `S3_BUCKET` — the C5 fix proven live.
- **Gotchas for next time:** (1) `docker cp` into the running container lands root-owned files —
  `exec -u root rm -rf` before re-copying tests; (2) presigned URLs percent-encode `=` in keys —
  compare via `urllib.parse.unquote`; (3) the runtime image excludes `tests/` by `.dockerignore`
  (copy them in for in-container runs).

## 2026-07-04 — B.2: Candidate timeline (append-only event store) ✅ (deployed + DB-proof)

Second Part-B task. Planned → built → **STOP-1 approved** → deployed → **append-only proven
on dev RDS as sps_app**.

- **Migration `0021_candidate_timeline`** (STOP-1 approved): `staffing.candidate_timeline` —
  bigserial PK, NO mixin (audit_logs shape, decision B), `tenant_id`/`business_unit_id`/
  `candidate_id`/`event_type`/`payload jsonb '{}'`/`actor_id NULL`/`occurred_at now()`, composite
  index `(candidate_id, occurred_at)`. Additive/reversible; local `up→down→up` + idempotency
  clean; applied to dev RDS by the pipeline (migrate-first, exit 0).
- **`app/timeline.py` (new):** `emit_timeline()` — INSERT-only, runs INSIDE the caller's txn
  exactly like `write_audit()`, so the endpoint's Idempotency-Key guard covers it (a replayed
  mutation returns the cached result before reaching the emit — proven by test). `EventType`
  constants for the full Part-18 catalogue; payloads are non-PII by contract (ids/stages/keys only).
- **Events wired now (7):** `Registration` (public register), `ResumeUpload` (B.1 TODO hook
  replaced), `Application` (create), `StageChange` (from/to in payload), `Submission`, `Offer`,
  `Interview` (workflow creates). **Deferred, constants only — NO fabricated call sites:**
  `TestCompletion` → TODO(B.7 assessment engine); `Joining`/`GuaranteeCompletion` → TODO(B.9
  placements); `ProfileUpdate` → skipped (no candidate-update endpoint exists yet).
- **Read endpoint:** `GET /api/candidates/{id}/timeline` — staff-only (`_require_staff` also
  rejects client-portal sessions → 403), tenant-scoped, chronological **ascending**
  (`occurred_at asc, id asc`), optional `?event_type=` filter, 404 out of scope. Soft-deleted
  candidates remain readable (erased/disabled people keep their de-identified history).
- **Append-only enforcement:** `bootstrap_app_role.py` extended —
  `REVOKE UPDATE, DELETE ON staffing.candidate_timeline FROM sps_app;` (+ comment on the
  default-privileges trap: master's ALTER DEFAULT PRIVILEGES grants full DML on every NEW table,
  so each new ledger MUST be added to the REVOKE list and the bootstrap re-run).
- **Tests: 118 → 126** (`tests/test_timeline.py` + a ResumeUpload assertion in test_resumes):
  emit-per-event; **idempotent replay appends exactly once**; asc ordering; `event_type` filter;
  registration emit; tenant-isolation 404; candidate-role 403; **client-session 403** (real
  client login). Manual over-the-wire check on local uvicorn: `["Application","StageChange"]`. ✅
- **Deploy + DB proof (the sequence that matters):** commits `eb41b75..58f33fd` (4 groups) →
  pipeline run `28699824127` green (migrate exit 0) → **bootstrap one-off task** (migrate
  task-def + `APP_DB_SECRET_NAME`) exit 0 ("append-only on audit_logs/consents/candidate_timeline")
  → **sps_app probe** (backend task-def, `scripts/probe_timeline_appendonly.py`): INSERT sentinel
  OK (id=1); UPDATE → `(psycopg.errors.InsufficientPrivilege) permission denied for table
  candidate_timeline`; DELETE → same error. **PASS, exit 0.** → **master cleanup** (migrate
  task-def, python -c): `deleted=1 remaining=0` (audit_logs-precedent tidy-up). Dev smoke:
  `/healthz`+`/readyz` ok, timeline endpoint 401 unauthenticated.
- **Gotcha for next time:** the sentinel/probe pattern needs THREE one-off tasks (bootstrap as
  master → probe as sps_app → cleanup as master) because sps_app cannot delete its own probe row
  post-REVOKE — that's the feature working, not a bug.

## 2026-07-04 — B.3: Duplicate detection — fuzzy + review queue + merge ✅ (deployed + real-op proof)

Third Part-B task. STOP-1 approved **including two ratified deviations** (below).

- **Migration `0022_dup_reviews_pg_trgm`** (STOP-1 approved): `CREATE EXTENSION pg_trgm`
  (public schema, citext precedent, ran as master in the pipeline migrate task);
  `staffing.candidate_dup_reviews` (bigserial, match_type/status CHECKs, `(tenant_id, status)`
  index) — a NORMAL business table, deliberately NOT in the bootstrap REVOKE list; GIN
  `gin_trgm_ops` index on `candidates.full_name` (prod note in the migration: build CONCURRENTLY
  on a populated table). Downgrade keeps the shared extension. Local `up→down→up` clean.
- **Model (create-then-flag, ratified):** intake ALWAYS creates the candidate (public register +
  staff create), then flags a `pending` review on a fuzzy hit. Exact dedup (blind-index unique →
  409) untouched — note: `app/dedup.py` did NOT previously exist (plan implied it did); exact
  lives in the unique constraints at the create sites, now documented in the new module.
- **Fuzzy scan (`app/dedup.py`):** `public.similarity(full_name, :name) >= 0.4`
  (`DEDUP_NAME_SIMILARITY`) AND a second signal — case-insensitive skill overlap OR resume-text
  trigram `>= 0.3` (`DEDUP_RESUME_SIMILARITY`). **Name alone never flags** (tested). Reads only
  non-encrypted fields (full_name/skills/resume_text) — no PII decryption anywhere. All calls
  schema-qualified (`public.similarity`) so resolution never depends on `search_path`; proven by
  a dedicated test through the app engine AND on real RDS as sps_app (probe step 1).
- **Endpoints** (staff, tenant-scoped, client-session 403): `GET /api/candidates/dup-reviews`
  (pending-first, paginated), `POST .../{id}/merge`, `POST .../{id}/dismiss` (both
  Idempotency-Key + audited; decided review replayed → 409 `REVIEW_NOT_PENDING`).
- **Merge integrity (one txn, never hard-deletes):** survivor = matched candidate, loser =
  incoming. Non-colliding applications repointed (submissions/offers/interviews carry only
  `application_id` → follow automatically — they have no candidate_id column, a correction to
  the plan's repoint list). **Collision rule** (`UNIQUE(job_id,candidate_id)` covers soft-deleted
  rows, so a redundant row can never be repointed): the surviving application ROW is always the
  survivor's; stage rank `rejected<on_hold<sourced<screened<assessed<submitted<interview<offer<
  placed`, further-along wins (tie → earlier created_at); if the loser's app was further along its
  stage is ADOPTED onto the survivor's row; the loser's row is archived IN PLACE with children
  attached. `vendor_submissions.candidate_id` repointed. Loser retired mirroring erasure:
  `phone_bidx`/`pan_bidx` nulled (frees the unique slots) + soft-deleted. `Merged`/`MergedInto`
  (new EventType constants, ratified) cross-link both records; `candidate.merge` audit with
  before/after.
- **RATIFIED DEVIATIONS:** `candidate_timeline` + `shared.consents` are **NOT repointed** on
  merge — both are append-only for sps_app (B.2 REVOKE / consents REVOKE), so UPDATE is
  physically impossible for the runtime role by design. The retained loser shell keeps those
  immutable rows anchored; the Merged/MergedInto events provide the cross-link.
- **Tests: 126 → 135**: similarity-resolution proof; exact 409 unchanged (+ never queues a
  review); fuzzy+skill-overlap flags on both intakes; name-alone guard; full merge assertions
  incl. the collision case; dismiss keeps both; tenant isolation (list empty for B, cross-tenant
  merge 404); client-session 403 on all three endpoints. Manual over-the-wire
  fuzzy→review→merge on local uvicorn: PASS.
- **Deploy + real-op proof:** commits `f728da2..d82a4f9` (4 groups) → pipeline run `28700689381`
  green (migrate exit 0 incl. CREATE EXTENSION) → **probe as sps_app on dev RDS**
  (`scripts/probe_dedup_merge.py`): `public.similarity()` resolves ✅ → fuzzy flag lands
  (review id=1, score **0.88**) ✅ → merge repoints the application, retires the loser
  (soft-deleted, bidx nulled), emits Merged+MergedInto ✅ — **PASS, exit 0**; probe business rows
  self-cleaned → **master cleanup** of the 2 orphaned probe timeline events (`deleted=2
  remaining=0`). Smoke: `/readyz` ok, dup-reviews endpoint 401 unauthenticated.
- **Gotchas:** (1) the application unique constraint covers soft-deleted rows — "archive then
  repoint" is impossible; adopt-stage-onto-survivor is the only shape that satisfies the
  constraint without data loss; (2) orphaned-merge-event cleanup SQL (`NOT EXISTS candidate`)
  precisely targets probe rows without touching real merge history.

## 2026-07-04 — B.4: Candidate search (Postgres FTS) ✅ (deployed + real-op proof)

Fourth Part-B task. STOP-1 approved.

- **Part-0 findings that shaped the build:** `search_doc` was already `tsvector` AND the GIN
  index already existed (`ix_candidates_search`, 0004) → migration `0023_search_doc_trigger`
  is **function + trigger + backfill only** (no duplicate index). Filter columns: `skills text[]`
  + `total_exp numeric` exist (filters live); `location`/`notice_period` absent — **skipped**.
- **Trigger (the erasure interplay rule, as implemented):** BEFORE INSERT OR UPDATE;
  `deleted_at IS NOT NULL → search_doc := NULL` (never recompute), else recompute from
  NON-encrypted fields only — `full_name` (weight A) + `skills` (B) + `left(resume_text,100k)`
  (C), config **'simple'** (names + tech tokens + multilingual content; English stemming adds
  variance without recall). Never touches email/*_enc — the index carries no PII beyond the
  already-plaintext name. Side benefit: disable-on-request (soft-delete) now de-indexes
  IMMEDIATELY, before anonymize. Backfill = no-op UPDATE firing the trigger.
- **Endpoint** `GET /api/candidates/search` (staff-only, client-session 403, tenant +
  `deleted_at IS NULL` scoped): `websearch_to_tsquery('simple', q)` with **standalone-AND
  normalization** (gotcha: `AND` is NOT a websearch operator — whitespace is — and 'simple' has
  no stopwords, so "Python AND AWS" would literally search "and"; the endpoint strips it,
  semantics unchanged; `or`/`-word`/quoted phrases work natively). `ts_rank` desc + created_at
  tiebreak, LIMIT 50; `skills` CSV → `@>` (existing GIN), `exp_min`/`exp_max` on total_exp.
  **Masked cards:** name/skills/exp + presence flags (`has_phone`/`has_pan`/`has_resume`) —
  never email/phone/pan.
- **Tests: 135 → 143:** setweight order (name>skill>resume, exact order asserted), boolean +
  exclusion, resume-only match, filters narrow + combine, trigger-on-update, **erasure interplay**
  (real /api/privacy/erase → search_doc NULL + absent), tenant isolation both directions,
  401/403 gates, masking (no PII keys, no plaintext leak). Manual over-the-wire: 14 ms local.
- **Deploy + real-op proof:** commits `15dd402..c09b840` (3 groups) → pipeline run `28701422136`
  green → probe as **sps_app on dev RDS** (`scripts/probe_search.py`): trigger populated
  search_doc on INSERT (3/3) → **A>B>C ranking correct in 5.6 ms** (<300 ms target) → skills+exp
  filter correct → **soft-delete → search_doc NULL + absent** ✅ — PASS, exit 0, self-cleaned (no
  timeline rows created → no master cleanup needed). Smoke: `/readyz` ok, search 401 unauth.
- **Test-hygiene gotcha:** a failed erasure-flow test can leave `dpdp_requests` FK'd to a test
  user, aborting teardown and cascading FK errors into later fixtures — user-cleanup helpers now
  delete dpdp_requests + memberships BEFORE the user (made `_mk_user` leftovers-robust).

## 2026-07-04 — B.5: Pipeline state-machine hardening ✅ (deployed + data-migrated + real-op proof)

Fifth Part-B task — the correctness slice. STOP-1 approved (mapping, hold_prior_stage
addition, reopen rule all ratified). First migration that REWRITES existing stage data.

- **Migration `0024_pipeline_stages`:** applications += `version` (optimistic lock, default 1),
  `hold_reason`, `drop_reason`, `hold_prior_stage` (reopen target — the one column beyond the
  planned set, ratified), `rtr_consent_at`/`rtr_consent_by`; consents purpose CHECK += `'rtr'`;
  stage CHECK dropped → **CASE data-migration** (`sourced→applied, screened→screening,
  assessed→aptitude_passed, submitted→submitted_to_client, interview→client_round_1,
  offer→offer, placed→joined, rejected→dropped [+tagged drop_reason], on_hold→on_hold`) → new
  21-value CHECK. Reversible (documented-lossy reverse map); **up→down→up proven with a live
  old-vocab row** (`submitted → submitted_to_client → submitted`). Prod note: batch + NOT
  VALID/VALIDATE on populated tables.
- **`app/pipeline.py` — the single stage-write module:** `transition()` (graph over the full
  Part-5 set; withdraw/drop from any non-terminal stage with REQUIRED reason → 422; on_hold
  stores prior stage; from on_hold only {prior, withdrawn, dropped}; reopen clears the hold
  bookkeeping; **RTR gate** 409 `RTR_REQUIRED` before submitted_to_client; **optimistic lock**
  via conditional UPDATE `WHERE version = expected` → 0 rows = 409 `STALE_STATE`; exactly one
  StageChange timeline + one audit row per transition, in-txn) and `adopt_stage_on_merge()`
  (the documented B.3 merge exception). STAGE_RANK + ACTIVE_STAGES live here — single
  vocabulary owner. **Grep-proof: zero stage writes outside pipeline.py.**
- **Endpoints:** `POST /api/applications/{id}/transition` (single public entry;
  `{to_stage, expected_version, reason?}`; staff, tenant-scoped, Idempotency-Key) and
  `POST /api/applications/{id}/rtr` (sets rtr_consent_at/by + appends the immutable `'rtr'`
  consent row; idempotent; audited). `PATCH /applications/{id}/stage` kept as a DEPRECATED
  shim through the guard (last-write-wins version; illegal moves still 409).
- **Rerouted/updated:** create_application initial stage `applied`; dup_reviews merge adoption
  via the guard module + new-vocab STAGE_RANK; employee SLA ACTIVE_STAGES from pipeline;
  client-portal funnel follows APPLICATION_STAGES; probe/e2e scripts; ALL legacy tests
  (incl. two client-portal fixtures with `stage="submitted"` that the Part-0 grep missed —
  caught by CheckViolation in the first local run, swept with a full 9-literal re-grep).
- **Tests: 143 → 156** (13 new): happy path applied→…→paid with the RTR block-then-pass +
  terminal proof; parametrized illegal matrix; reasons; hold/wrong-reopen-409/reopen-clears;
  stale-CAS (graph-legal move + old version); one-timeline+one-audit with idempotent replay;
  shim-through-guard; scoping. Manual over-the-wire walk incl. STALE_STATE + withdraw: PASS.
- **Deploy + real-op proof:** commits `feaee3d..6c81961` (4 groups) → pipeline run
  `28702832371` green (migrate log shows 0024 applied, exit 0) → probe as **sps_app on dev
  RDS** (`scripts/probe_pipeline.py`): **DISTINCT-stage check = no old-vocabulary values
  remain** ✅ → 6 legal transitions (version 1→7) ✅ → RTR gate 409 ✅ → stale-CAS 409 ✅ →
  withdraw-with-reason + exactly 7 StageChange rows ✅ — PASS exit 0 → master cleanup
  `deleted=7 orphans_remaining=0`. Smoke: `/readyz` ok; transition + rtr endpoints 401 unauth.
- **Gotchas:** (1) a replayed same-target transition hits ILLEGAL_TRANSITION before the CAS —
  a stale-version test must use a graph-legal move from the CURRENT stage; (2) crashed-run
  leftovers (users with memberships + old-vocab seeded rows) can exhaust the tiny local pool
  (2+2) via cascading fixture failures and masquerade as a leak — `_mk_user` helpers are now
  leftover-robust; (3) NEW DEFERRAL: the local frontend kanban still sends old stage names —
  functionally broken against the new vocabulary until updated (PENDING D5).

## 2026-07-04 — B.6: Internal evaluation rounds as gated stages ✅ (deployed + real-op proof)

Sixth Part-B task — deliberately small: B.5 already owned the stages/graph/gate; B.6 adds the
recording layer + the explicit invariant proof. STOP-1 approved (table storage + TestCompletion
wiring, both per the stated defaults).

- **Migration `0025_internal_evaluations`:** first-class R1/R2 records (round 1|2 CHECK,
  pass|fail CHECK, evaluator_id, notes, occurred_at) + `(application_id, round)` index.
  Normal-DML table — confirmed NOT in the append-only REVOKE list. `up→down→up` clean.
- **`POST /api/applications/{id}/evaluations` {round, result, notes?, expected_version?}**
  (staff, tenant-scoped, Idempotency-Key, audited): `(1,pass)→aptitude_passed`,
  `(1,fail)→aptitude_failed` (both + **TestCompletion** timeline event — the constant waiting
  since B.2; code-comments that B.7's engine becomes a second emitter), `(2,pass)→
  internal_passed`, `(2,fail)→dropped` **via the guard's drop-with-reason path**
  (`'failed internal technical'`). Stage effects EXCLUSIVELY through `pipeline.transition()`;
  the evaluation row and the transition share ONE txn, so an illegal recording (guard 409)
  rolls the record back — proven by test. Out-of-order rejection is the graph's own (no
  parallel check to drift).
- **THE INVARIANT (the point of the slice), proven twice:** parametrized test — from EVERY
  pre-internal stage (applied, screening, aptitude_test, aptitude_passed, aptitude_failed,
  internal_interview) a direct `/transition` to submitted_to_client → 409 ILLEGAL_TRANSITION;
  the full legit path (R1 pass → internal_interview → R2 pass → rtr_pending → RTR → submit)
  succeeds. No shortcut to submit exists.
- **Tests: 156 → 168.** Manual over-the-wire walk PASS (shortcut 409 + full path).
- **Deploy + real-op proof:** commits `de4f0e1..e145d21` (3 groups) → pipeline run
  `28703300449` green (migrate exit 0) → probe as **sps_app on dev RDS**
  (`scripts/probe_evaluations.py`): no-shortcut invariant ✅ → R1 pass → aptitude_passed +
  TestCompletion row ✅ → R2 pass → RTR → submitted_to_client with 2 evaluation rows ✅ —
  PASS exit 0 → master cleanup `timeline=8, rtr consents=1, remaining=0` (note: the probe's
  'rtr' consent row is append-only for sps_app, so the master cleanup now also sweeps
  orphaned rtr consents — pattern extended from B.2/B.3). Smoke: `/readyz` ok, endpoint 401.
- **Gotcha:** any probe that exercises the RTR gate necessarily writes an immutable consents
  row — master-cleanup JSON must include the orphaned-'rtr'-consent sweep, not just timeline.

## 2026-07-04 — B.7: Proctored aptitude test engine + admin waiver ✅ (deployed + real-op proof)

Seventh Part-B task — the flagship differentiator. Combined STOP-1 (core + waiver) approved.
Introduces the platform's FIRST non-JWT auth surface.

- **Migration `0026_aptitude_tests`:** `question_banks` / `questions` (difficulty CHECK;
  `correct_index` server-side only) / `tests` (SHA-256 `link_token_hash` UNIQUE, `valid_until`,
  status CHECK issued|started|submitted|expired, `attempt_no`, FROZEN `served_questions` jsonb,
  score/passed, `proctor_flags` jsonb). Normal-DML (not in the REVOKE list). **Seed:** 12
  clearly-marked SAMPLE questions (SPS001, in-migration, online-mode) — real content is a Part-C
  input. up→down→up clean (seed=12 verified).
- **TOKEN AUTH MODEL (new trust surface):** `secrets.token_urlsafe(32)` (256-bit CSPRNG), stored
  as SHA-256 only (raw shown once at issue; indexed-equality lookup — stretching pointless for a
  CSPRNG secret). The token resolves exactly ONE test row; tenant/candidate/application derive
  from that row only. `/api/take` has zero JWT/cookie code paths — a staff JWT is useless there
  (tested). Unknown → 404; expired/used/waived → 410; uniform bodies, no enumeration signal.
- **ANTI-CHEAT CORE:** at issue — CSPRNG weighted-random select (even across difficulties),
  question AND option shuffle, exact served set + post-shuffle correct answers FROZEN into
  `served_questions`. Fetch returns `{qid, stem, options}` only (test asserts the literal
  "correct" absent from the response). `grade()` reads ONLY the frozen copy — post-issue bank
  sabotage test (flip all answers + deactivate all questions) still grades 1.0. Score =
  correct/total, no negative marking, pass ≥ 0.70 (config; boundary tested). Idempotent submit.
- **THREE R1 EMITTERS, mechanically single-fire:** engine (take submit), B.6 manual evaluation,
  admin waiver — all drive the same `aptitude_test → aptitude_passed|failed` guard edge, and the
  edge IS the mutex: first mover wins; later attempts 409 (manual/waiver) or store-without-
  advancing (engine, `pipeline_advanced:false`, no event). TestCompletion payload carries
  `source: engine|manual… (B.6 emits without source)|admin_waive`. Both orders tested, event
  count asserted = 1.
- **ADMIN WAIVER (governed per-tenant capability):** `FEATURE_ASSESSMENT_WAIVER` (default OFF →
  404 probe-proof, ctx-aware resolver for later per-tenant/plan resolution) + `_require_admin`
  (recruiters 403) + reason REQUIRED (422) + audited (`test.waive`). Honesty: `score` stays NULL
  (never a fake number), `proctor_flags.waived={by,reason,at,source:'admin_waive'}`, dashboard
  exposes `waived:true` — a waived pass is structurally distinguishable. Mutual exclusion both
  directions: graded → waive = 409 ALREADY_GRADED; waived → take fetch/submit = 410. Waived FAIL
  follows the same retake cooldown. **Invariant preserved:** a waived R1 still can't jump to
  submitted_to_client (R2 + RTR required — tested).
- **Also:** issue preconditions (stage `aptitude_test` / one live test / 30d retake cooldown with
  `attempt_no++` + fresh paper), snapshot presign under the candidate's `/proctor/` S3 prefix
  (upload only — the browser capture loop is frontend, deferred), staff dashboard (never exposes
  the paper or token hash), result email stubbed pending B.10/SES.
- **Tests: 168 → 186.** Manual walks: core run + waiver walk (incl. over-the-wire flag-OFF 404).
- **Deploy + real-op proof:** commits `2b2e707..150dd1c` (4 groups) → pipeline run `28704532125`
  green (migrate + seed) → probe as sps_app (`scripts/probe_assessments.py`): seed=12 ✅ →
  freeze + no-leak ✅ → auto-grade + aptitude_passed + TestCompletion ✅ → snapshot presign +
  **REAL PUT to the real bucket** + key in proctor_flags + object deleted ✅ → **waiver leg:
  flag-OFF 404 → flag-ON waive → aptitude_passed, score NULL, waived block, ONE
  TestCompletion{admin_waive}** ✅ — PASS exit 0 → master cleanup `orphaned timeline=8,
  remaining=0`. Smoke: `/readyz` ok, bad token 404, issue 401 unauth, waive 401 unauth
  (authenticated flag-off 404 proven by probe/tests).
- **Gotcha:** unauthenticated waiver calls 401 before the flag's 404 (auth dependency resolves
  first) — the probe-proof property applies to authenticated probing, which is the threat the
  pattern addresses.

## 2026-07-04 — B.8: Interview scheduling depth (slots, .ics, no-show/reschedule) ✅ (deployed + real-op proof)

Eighth Part-B task. STOP-1 approved (.ics eyeballed valid; DDL + waiver pin praised).

- **Migration `0027_interview_slots`:** slot table (>=3 per round, one chosen, DB-level
  `slot_end > slot_start` CHECK), status CHECK widened with `rescheduled` ONLY (Part-0 catch:
  `no_show` existed since 0013 — smaller blast radius), interviews += `ics_sequence`
  (RFC 5545 SEQUENCE must persist to bump) + `status_reason` (no-show reason — `feedback` is
  client feedback, wrong container). Reversible (`rescheduled→scheduled` before CHECK restore).
- **`app/ics.py`:** hand-rolled RFC 5545, no new dependency — stable
  `UID:interview-<id>@spstechnosoft.com` + SEQUENCE bump on reschedule (calendar clients update
  in place), DTSTAMP/DTSTART/DTEND UTC Zulu, CRLF, TEXT escaping, METHOD:REQUEST with
  ORGANIZER/ATTENDEE. **Noted for the future cancel path (B.10 email era):** cancellation wants
  `METHOD:CANCEL` + `STATUS:CANCELLED` + SEQUENCE bump so calendars actually remove the event;
  panel interviews may want multiple ATTENDEEs (interviewer currently DESCRIPTION-only).
- **Endpoints (staff, tenant-scoped, idempotent, audited):** propose (>=3 or 422 TOO_FEW_SLOTS;
  re-proposal replaces the unchosen round) → choose (one chosen, `scheduled_at` set, timeline
  `Interview{action:scheduled}`) → `GET /interviews/{id}/ics` download (SES attach = B.10).
  PATCH: `no_show` REQUIRES reason (422 REASON_REQUIRED → `status_reason`); `rescheduled` bumps
  SEQUENCE, wipes the slot round (fresh .ics on next choose), emits
  `Interview{action:rescheduled}`. **No pipeline coupling** (Part-0 verified: pipeline.py has
  zero Interview references — scheduling can never move a stage). Client portal surfaces the new
  status read-only with no code change (status passes through verbatim; tested).
- **Step-0 carry-over — B.7 waiver boundary PINNED:** 6 tests — recruiter/employee/coordinator/
  business_manager/candidate (flag ON, parametrized) all 403; client_admin + client_manager
  portal sessions 403. No code change needed (`_require_admin` held); the admin-only guarantee
  is now regression-locked.
- **Tests: 186 → 197.** Manual walk PASS (propose→choose→.ics SEQUENCE:0→reschedule→SEQUENCE:1
  w/ new DTSTART→no-show-with-reason).
- **Deploy + real-op proof:** commits `3279321..591d8fd` (4 groups) → pipeline run
  `28705117267` green → probe as sps_app (`scripts/probe_interview_slots.py`): slots table live
  (3 proposed) → choose + valid .ics (UID/SEQUENCE:0/CRLF) → reschedule SEQUENCE=1 + round wiped
  → no_show + reason persisted on the widened CHECK + Interview timeline row — **PASS exit 0**
  → master cleanup `orphaned timeline=1 → 0`. Smoke: `/readyz` ok, slots + ics endpoints 401
  unauth (authenticated .ics content proven by the probe).

## 2026-07-04 — B.9: Commercial layer — placements, guarantee, replacement, commission, invoice PDF ✅

Ninth Part-B task. STOP-1 approved with the founder-confirmed FEE MODEL (resolves C.2).

- **FEE MODEL (Part 0-FEE, ratified):** base = **ANNUAL CTC** (schema evidence:
  `offers.ctc` documented annual since 0012; no monthly semantics anywhere — verified);
  **15% flat default, before tax**; **client-level override** (`clients.fee_percent NOT NULL
  DEFAULT 15`, migration 0028) with per-call override on top — resolution order
  **invoice override → client rate → global 15** (`_resolve_fee_percent`, test-locked);
  **GST/TDS inert** until C.3 — total == fee, and the PDF never presents it as taxed.
- **Migration `0028_placements`:** placements (offered_ctc ANNUAL, joined_on/guarantee_until
  with a DB CHECK `guarantee_until >= joined_on`, status CHECK incl. forward-compat
  'in_guarantee', breach_reason, replacement_for self-FK, indexes on application_id +
  guarantee_until) + clients.fee_percent + invoices.{placement_id, is_replacement,
  credit_note_of}. Normal-DML; REVOKE list untouched. up→down→up clean.
- **GUARANTEE CLOCK (the design that matters):** the SOURCE OF TRUTH is
  `derived_guarantee_state()` — pure date math on read, correct even if no job ever runs
  (breached/replaced explicit; else window decides). `guarantee_sweep()` only MATERIALIZES
  active→cleared + ONE GuaranteeCompletion, status-guarded → double runs are no-ops and
  missed runs self-heal. Runner = `scripts/run_commercial_jobs.py` one-off ECS task (repo
  pattern; NO Celery, nothing always-on/paid); production wiring = EventBridge Scheduler →
  ECS RunTask, deferred (free, PENDING).
- **REPLACEMENT / NO-DOUBLE-FEE:** breach (reason REQUIRED; only within the derived window)
  → 'breached' + GuaranteeCompletion{breached} + **requisition reopened via the EXISTING
  jobs.status='open' flag** (no new pipeline edge, no stage rewind). Replacement = same-job
  joined application, `replacement_for` link, fresh 60d guarantee, **NO invoice** — revenue
  reporting sums invoices, so double-counting is structurally impossible (test-locked:
  exactly one fee invoice after the full breach→replace cycle). Refund = explicit
  credit-note structure (one per original, negative fee mirror, GST untouched).
- **Commission attribution:** placements.recruiter_id (from the application owner);
  `GET /placements/commissions` = per-recruiter count + billed fees (credit notes excluded;
  replacements naturally absent). **Invoice PDF:** ReportLab (new dep, ARM64-clean) — fee as
  one line item, GST/TDS present-but-"pending" lines, total labeled PRE-TAX, numbering
  clearly PROVISIONAL (format = C.3 input); rendered → S3 → presigned GET. **Dunning:**
  detection only (`GET /invoices/overdue` + sweep); send stubbed until B.10/SES.
- **Timeline:** Joining + GuaranteeCompletion — the last two B.2 constants — now have their
  first emitters. Every EventType is live.
- **Tests: 197 → 207.** Deploy: commits `b47ef8a..6394c98` (4 groups) → pipeline run
  `28707568160` green → **probe as sps_app** (`scripts/probe_placements.py`): client-fee
  resolution (1,000,000 × 12% = 120,000, annual base) → derivable-without-job → sweep 1-then-0
  + single event → breach/reopen/replacement with NO second invoice → **PDF → real S3 PUT +
  presigned GET + object deleted** — PASS exit 0 → master cleanup `orphaned timeline=5 → 0`.
  Smoke: `/readyz` ok, placements + overdue endpoints 401 unauth.
- **Gotcha (test-infra, for the record):** two pytest suites accidentally run CONCURRENTLY
  against the local DB + 2+2 pool → mass TimeoutError/CheckViolation storm that looks like a
  code defect; the giveaway is failures spread across unrelated files + multi-minute runtimes.
  Fix = one serial run after a pool restart + leftover sweep (207 green in 22.6s). Also: the
  new `ck_placements_guarantee_order` CHECK caught an incoherently back-dated test row —
  defense-in-depth paying for itself immediately.

## 2026-07-04 — B.10: Notification service scaffolding ✅ (deployed + real-op proof)

Tenth Part-B task — the keystone that un-stubs B.7 result / B.8 reminder / B.9 dunning.

- **TRANSPORT (settled):** the `shared.notifications` TABLE + the one-off runner sweep — queue,
  delivery-status, idempotency ledger and audit in ONE store; no Redis queue (a second store to
  reconcile); worker = future scale-up behind the same interface. Sweep lives in
  `run_commercial_jobs.py` (single runner for all periodic work).
- **Migration `0029_notifications`:** `notification_templates` (versioned, UNIQUE code) +
  `notifications` (status CHECK pending|sent|failed|skipped, `UNIQUE(idempotency_key)` — the
  DB-level no-double-send guarantee, `(status, created_at)` sweep index). Deliberately
  UPDATE-in-place OPERATIONAL tables (unlike the append-only ledgers) — NOT in the REVOKE
  list. Seeds: 3 PROVISIONAL operational templates; legal/consent copy stays STOP-3.
- **THE PART-D SEAM (`app/notify.py`):** `AbstractChannel.send(RenderedMessage)→DeliveryResult`
  with self-declared `channel_type`; `CHANNEL_REGISTRY` decides deliverability. Only
  **ConsoleChannel** (log-only dev sink) is registered; Email/Sms/WhatsApp are DECLARED but
  off. **Registering a real channel (+ clearing `NOTIFY_CHANNEL_OVERRIDE`) is the entire Part-D
  switch — zero call-site changes.** Unregistered channel rows PARK pending, untouched by the
  sweep (attempts not burned) → Part D picks them up automatically. `NOTIFY_CHANNEL_OVERRIDE`
  (default `console`) routes dev enqueues to the sink while templates keep their intended
  channel.
- **Idempotency:** stable business keys — `assessment_result:<test_id>`,
  `interview_reminder:<interview_id>:<ics_sequence>` (reschedule = new reminder; replay ≠ dup),
  `invoice_dunning:<invoice_id>` (one notice per invoice; cadence = Part-D policy). Duplicate
  enqueue = no-op; sweep processes `pending` only → sent rows structurally unresendable.
- **Consent:** TRANSACTIONAL kinds (result/reminder/dunning) are operational service messages
  under the service's lawful basis — no marketing gate. `kind='marketing'` checks the
  `shared.consents` ledger (latest 'marketing' for the subject); absent/withdrawn →
  `skipped` + reason recorded, never sent. Retry: attempts cap (`NOTIFY_MAX_ATTEMPTS`=5),
  `last_error` recorded, `failed` at cap, backoff = runner cadence.
- **Wired sites (enqueue only, never direct send):** take.py submit; workflow.py choose_slot
  (.ics attach + METHOD:CANCEL live inside the future EmailChannel); jobs.py dunning_sweep —
  runner-only `enqueue_sends=True` so `GET /invoices/overdue` stays read-only; dunning
  recipient = the client's first active bound user (none → detection-only, logged).
  Plus `GET /api/notifications` (staff, tenant-scoped status/debug view).
- **Tests: 207 → 216.** Manual walk PASS (trigger → pending row → sweep → verbatim CONSOLE
  DELIVERY log → sent). Deploy: commits `5308a21..764fbda` (4 groups) → pipeline run
  `28708541258` green → probe as sps_app: seeds ✅, idempotent enqueue ✅, sweep sent-once +
  idempotent re-run ({'sent':1}→{'sent':0}) ✅, email row parked untouched ✅ — PASS exit 0,
  self-cleaned. Smoke: `/readyz` ok, notifications endpoint 401 unauth.
- **PII note (PENDING B4 invariant):** the notifications table stores recipient + rendered
  operational bodies (names/schedules) — PII-adjacent; keep it out of any future cache path.
  ConsoleChannel is log-only, never a durable store.

## 2026-07-04 — B.11: Founder dashboard (read-models + Redis cache) ✅ (deployed + real-op proof)

Eleventh Part-B task — read-heavy, security-first. A NO-MIGRATION slice.

- **MATERIALIZATION (settled):** on-read aggregation + Redis cache for v1 — dev volume is tiny
  and correctness-on-read is simpler to prove; nightly materialized read-model tables are the
  volume scale-up, added later behind the same `app/reporting.py` functions (PENDING D9).
- **THE GATE (the headline):** `FOUNDER_ROLES = {owner, super_admin, founder}` — 'owner' is
  the founder's actual seeded slug (0003); plain **admin is deliberately excluded** (stricter
  than the admin gate); client sessions always rejected. Recruiter-performance/client-health
  aggregates therefore never reach the people they describe. **Every access audit-logged**
  (`dashboard.founder_access`: endpoint, metric, range, refresh) — test-locked to exactly one
  row per access. Tenant-scoped in every query AND cache key — no cross-tenant totals exist.
- **NO-PII-IN-REDIS, BY CONSTRUCTION (PENDING B4 upheld):** `cache_guard()` runs on every
  cache write and on export payloads — dict keys must be enumerated ALLOWED_FIELDS / known
  labels / date buckets; values only numbers/bools/None / CHECK-constrained labels (stages,
  BU codes, statuses, template codes) / `YYYY-MM` buckets. Names, emails, free text raise
  `CacheGuardError` before any Redis write. Test-locked (rejections + real-shape passes) AND
  probe-verified against real ElastiCache (cached JSON re-guarded + inspected).
- **Cache model:** `dash:founder:<tenant>:<bu|all>:<metric>:<range>`, TTL 300s, `?refresh=1`
  deletes-then-recomputes; Redis outage degrades to compute (optimization, never dependency).
- **Endpoints:** `/api/dashboard/founder/{overview,trends,by-bu,export}` — trends metrics
  allowlisted (revenue/placements/applications, month-bucketed); **by-bu shows
  ACADEMY/CONSULTING present-but-zero via the same real queries** (not fabricated). Exports:
  PDF (ReportLab) + xlsx (**openpyxl — new pure-Python dep, ARM64-clean**); tests extract both
  and assert no candidate name appears anywhere.
- **Tests: 216 → 224.** Guard iteration for the record: v1 of the guard rejected its own
  payload FIELD NAMES — resolved with the enumerated-fields-for-keys / labels-only-for-values
  split (stricter where data flows, safe where literals flow).
- **Deploy + real-op proof:** commits `a6ba03d..6b1d5a6` (3 groups) → pipeline run
  `28709399486` green (migrate no-op at head 0029, as expected) → probe as sps_app (founder
  exercised via in-process owner-role context — dev has no browser login, JWT = Part D; the
  gate additionally proven by recruiter/client contexts 403ing): seeded KPIs match on real RDS
  → **real ElastiCache key inspected, cached value passes the PII guard, no '@'/names in the
  raw JSON** → refresh + audit row → PDF/xlsx round-trip — PASS exit 0, self-cleaned (cache
  keys deleted; probe audit rows kept — genuine access records). Smoke: `/readyz` ok, founder
  endpoint 401 unauth.

## 2026-07-04 — B.12: CRM / lead management ✅ (deployed + real-op proof)

Twelfth Part-B task — kept deliberately tight; the reuse shape is the point.

- **SHARED SCHEMA (settled A):** `shared.leads` + `shared.activities` (migration
  `0030_crm_leads`) — staffing BD uses them now; Consulting (B.18) reuses the SAME
  tables/endpoints via `business_unit_id` scoping. Test + probe locked: a CONSULTING lead in
  the same tenant is invisible to the STAFFING context (list AND direct fetch 404). Lead
  contact fields are BUSINESS contacts (BD card data, same class as client/vendor contacts)
  → plaintext, ratified. Normal-DML; REVOKE list untouched.
- **MINI GUARD (settled B, pipeline.py shape):** `transition_lead()` is the only stage
  writer — linear `new→qualified→proposal→negotiation→won`; `lost` from any non-terminal
  WITH required reason (422 mirror of B.5 drop/withdraw); won/lost terminal; illegal 409;
  every move drops an activity row + audit.
- **Activities:** dedicated user-facing stream (`created`/`call`/`stage_change`/`converted` …
  chronological per lead) — audit_logs is the system trail, candidate_timeline is
  candidate-anchored; both wrong containers.
- **CONVERT (settled C — staffing branch only):** requires `stage='won'` (409 otherwise);
  creates one staffing client + optional job intake; **idempotent via
  `converted_client_id`** — double convert returns the same client (COUNT==1 asserted on
  real RDS). CONSULTING branch = 400 `NOT_BUILT` + TODO(B.18), same constants-only
  discipline as B.2's deferred events.
- **Tests: 224 → 230.** Manual walk PASS. Deploy: commits `c7785cb..986ad14` (3 groups) →
  pipeline run `28710230404` green → probe as sps_app: stage walk ✅, lost-reason enforced ✅,
  convert + double-convert n=1 ✅, BU-scoping invisibility ✅ — PASS exit 0, self-cleaned.
  Smoke: `/readyz` ok, leads endpoint 401 unauth.

## 2026-07-04 — B.13: Vendor management depth ✅ (deployed + real-op proof, incl. cross-slice)

Thirteenth Part-B task — closes PENDING D3. Both STOP-1 flags confirmed by the architect.

- **CLIENT-DYNAMIC COMMISSION (settled + confirmed):** resolution most-specific-wins —
  per-placement override → `vendor_client_rates` (vendor×client TABLE; a rate matrix needs a
  table) → `vendor_contracts` base **valid AT placement.joined_on** → global default. The
  resolver returns `(percent, source_level)` and PERSISTS the level into the audit trail —
  when a commission is disputed later, the audit says which level resolved it.
- **COMMISSION BASE = % of the PLACEMENT FEE (confirmed):** a share of SPS's earnings, never
  CTC — %-of-CTC would pay ~6.7× more at a 15% fee and silently destroy vendor-placement unit
  economics. Hand-locked: fee 150,000 × 8% = 12,000.
- **GLOBAL DEFAULT = None (confirmed — the C.2 lesson):** `VENDOR_COMMISSION_DEFAULT_PERCENT`
  ships unset; nothing resolving → 409 `NO_COMMISSION_BASIS` rather than an invented
  commercial term. **The vendor global default % is now a pending BUSINESS INPUT** (PENDING),
  live the moment the founder names a number.
- **MATERIALIZED + RATE LOCK (migration `0031_vendor_depth`):** the valid-at-placement-date
  guarantee requires persistence — `vendor_commissions` locks percent/base/amount at accrual
  (post-accrual rate change proven not to retro-alter, locally + on real RDS);
  `UNIQUE(placement_id)` = structural one-commission-per-placement; lifecycle accrued→paid|void
  (paid cannot be voided here — money that left needs explicit handling; void requires reason).
- **NO-DOUBLE-COUNT NET:** replacements 409 (no fee, consistent with B.9) · duplicate accrual
  409 + DB unique · credit-noted fees refuse accrual · **credit-noting a fee AUTO-VOIDS an
  ACCRUED commission in the same txn (audited `auto:true`)** — the one place B.13 modifies B.9
  behavior, and per the architect's ask it is REAL-OP PROVEN: probe leg 6 credit-noted a
  commissioned fee on dev RDS → commission voided in-txn → audit row with auto:true → scorecard
  accrued→0. Paid commissions deliberately NOT auto-voided (accrued/paid distinction).
- **SOURCING-TRAIL INTEGRITY (beyond spec, kept):** accrual requires a `vendor_submission`
  linking the vendor to the placed candidate (job-matched when set); no trail → 409
  `NO_SOURCING_TRAIL`; multi-vendor ambiguity → 409 `AMBIGUOUS_VENDOR` (refuse, never guess who
  gets paid) — closes a vendor-misattribution/fraud surface.
- **Scorecard:** on-read read-model (B.11 pattern, no table): submissions, placements,
  conversion, avg time-to-fill, in-guarantee actives, accrued/paid totals. Vendor-submission
  create endpoint already existed (workflow.py) — untouched; its UI stays frontend-deferred.
- **Tests: 230 → 237.** Deploy: commits `c10d63e..80f0f45` (3 groups) → pipeline run
  `28711719316` green → probe as sps_app: client-rate-beats-contract (12% vs 8%) ✅ →
  rate-lock ✅ → dup 409 ✅ → scorecard ✅ → **cross-slice credit-note auto-void ✅** — PASS
  exit 0 → master cleanup `orphaned timeline=1 → 0`. Smoke: `/readyz` ok, endpoints 401.

## 2026-07-04 — B.5-fix: two endpoints 500ing since B.5 + the route-smoke class-guard ✅

Micro backend slice (STOP-1-exempt, NO migration — head stays 0031). Found while starting F1:
the frontend kanban's data source was dead.

- **THE REGRESSION:** `staffing.py` kept two function-body references to the TRANSITIONS dict
  B.5 deleted — module imports fine, endpoints NameError at request time:
  `GET /jobs/{id}/pipeline` and `GET /client-portal/overview` **500 on every call since the
  B.5 deploy**, locally and on dev. The overview ALSO queried dead stage literals
  ('interview', 'placed', a funnel over the pre-B.5 names) — a name-only fix would have
  returned permanent zeros.
- **ROOT CAUSE OF THE ESCAPE:** B.5's blast-radius grep hunted stage WRITERS and vocabulary
  literals in stage-value positions; these were READERS referencing the deleted dict object —
  matched neither. And both endpoints predate the per-slice test discipline: ZERO coverage,
  so 237 green tests coexisted with two shipped 500s.
- **THE FIX:** job_pipeline seeds buckets from APPLICATION_STAGES (the vocabulary owner).
  employer_overview REBUILT on the current vocabulary, response shape unchanged:
  in-pipeline = NOT post-join AND NOT withdrawn/dropped · interviews = client_round_1..3 ·
  placements = joined/guarantee/invoiced/paid · funnel grouped over real stages
  (Screening/Assessment/Internal/Submitted/Client Rounds/Offer/Joined).
- **THE SWEEP FOUND ONE MORE (same class, fixed):** `client_portal.py` declared a LOCAL
  pre-B.5 copy of APPLICATION_STAGES shadowing the models constant (B.5's Part-0 wrongly
  assumed it imported it) — the client pipeline view pre-seeded dead-stage buckets. Now
  imports the owner; local re-declarations of the vocabulary are banned by comment.
- **THE CLASS-GUARD (permanent):** `tests/test_route_smoke.py` — every GET /api route is hit
  under BOTH recruiter and owner sessions with seeded path params (moto for S3-touching
  routes); none may return 5xx. **It found no OTHER latent 500s today** — the two known ones
  were the full extent. Plus non-zero-count regression tests for both endpoints.
- **Tests: 237 → 240.** Deploy: commits `e1c4261..2ca4b32` → pipeline run `28712493795` green
  (migrate no-op, head 0031) → probe as sps_app on dev: pipeline 21 buckets + rows placed ✅,
  overview NON-ZERO new-vocabulary counts (funnel hits Screening/Client Rounds/Joined) ✅ —
  PASS exit 0, self-cleaned. `/readyz` ok.
- **Lesson recorded:** blast-radius greps must hunt READERS of deleted objects, not just
  writers/literals; and the route-smoke matrix now guards the whole GET surface on every run.

## 2026-07-04 — F1: Frontend foundation — marketing→login→role-routed dashboards ✅ (local-verified)

First FRONTEND slice (frontend-only; paths-ignore confirmed — no backend deploy). Next.js
15.5.19 / React 19.2.7 confirmed. "Done" = built + locally verified; hosting stays Part D.

- **Design language:** the working frontend descends from the `Context/spstechnosoft-platform`
  reference starter — brand tokens (sps-blue/navy/gold, page/card surfaces, navy sidebar),
  Sora+DM Sans type, and the AppShell/kit all carried over intact. F1 additions: `ComingSoon`
  (the stable placeholder for deferred deep screens), `FounderKpiStrip`, topbar **Sign-out**
  (the shell previously had NO logout).
- **Role routing (reused, wired):** login → backend `home` (owner/admin→/admin/dashboard,
  staff→/employee, client→/client, candidate→/candidate); edge middleware bounces wrong-role
  access; client-bound sessions can only reach /client. **/employer/\* re-homed to the employee
  role** — they were stranded on the client role after the client-portal split and unreachable
  by ANYONE (PENDING D4b resolved); recruiters now reach pipeline/jobs/submissions/interviews/
  offers/invoices/vendors from the employee nav.
- **Dashboards with real headline data:** candidate /me/overview · employee /employee/overview ·
  client /client/overview (all pre-existing) · **admin landing rebuilt** (real candidates/
  clients/jobs totals + manage links) · **founder KPI strip** on the admin dashboard — renders
  only when the founder gate passes; a plain admin's 403 hides it gracefully (verified 200/403
  through the proxy). Deep screens = nine ComingSoon pages (previously 404ing nav targets).
- **D5 kanban:** columns rewritten on the CURRENT B.5 vocabulary — 14 rank-ordered forward
  stages as drag targets + read-only post-join/closed tail columns, friendly labels. **HONEST
  shim status: stage changes still ride the deprecated last-write-wins PATCH shim — pipeline
  rows don't expose `version`, so optimistic-lock POST /transition is a tracked backend
  follow-up (PENDING).**
- **Verified:** tsc + eslint clean; next build green; 24-check manual walk PASS against the
  local backend (marketing → /services/staffing login entries → each of 5 roles lands on its
  correct home; wrong-role bounces incl. client→/employer; logout kills access). Commit
  `54d6d98`; no pipeline run triggered (frontend paths-ignored).

## 2026-07-04 — F2: kanban optimistic locking (F2a backend micro + F2b frontend) ✅

- **F2a (backend micro, deployed):** `version` now rides every application row via `_app_dict`
  (pipeline rows, create responses, the shim's own response). Additive; no migration (head
  0031). Tests 240→241 (version-on-rows regression). Pipeline run `28713416638` green; dev
  smoke printed a live row with `"version": 1`. Commit `74a096d`.
- **F2b (frontend, local-verified): THE SHIM IS RETIRED** — `useChangeStage` (PATCH
  last-write-wins) deleted; `useTransitionStage` posts `/transition` with expected_version.
  409 UX by error code: STALE_STATE → "board changed elsewhere" + auto-refetch ·
  ILLEGAL_TRANSITION → clean rejection · RTR_REQUIRED → collect-RTR guidance · drop/withdraw
  open a REASON MODAL up front (server 422 surfaced if bypassed). rtr_pending cards carry an
  RTR chip + disabled Submit. Hold/reopen affordances. Card click → side panel (candidate
  context, live stage+version, append-only timeline, deep actions marked upcoming).
  **PENDING D11 CLOSED.** Verified: tsc/eslint/build clean + a 7-check API walk covering every
  error path end-to-end (PASS). Commit `4e39ba0`, frontend-only, no deploy triggered.
- **Scope item raised, not silently skipped:** candidate portal tabs need BACKEND surface that
  doesn't exist (`/me/applications`, a user→candidate linkage rule, real `/me/overview` counts
  — the old Slice-2 zeros TODO). Stopped per the F2b backend guard; proposed as F3a
  (micro backend) + F3b (the tabs).

## 2026-07-04 — F3: candidate↔user linkage (F3a backend) + candidate tabs (F3b) ✅

- **F3a (backend, STOP-1 approved, deployed):** migration `0032` — `candidates.user_id`,
  an EXPLICIT soft ref to shared.users (no cross-schema FK, matching jobs.owner_user_id;
  runtime resolution never email-matches). Registration creates no User (stated, per the
  rule's parenthetical) — the auto-link materializes only when the registrant already has a
  candidate/student login. **Merge linkage (the provably-correct piece):** survivor keeps its
  own · loser-only moves over · **both-different proceeds but FLAGS durably** — append-only
  audit `candidate.merge_link_conflict` + timeline `MergeLinkConflict` (both user ids), and
  the loser RETAINS its user_id soft-deleted → zero data loss, staff can re-link. New
  `/me/applications` (live stages; unlinked → [] 200) + `/me/overview` rebuilt with real
  counts (the Slice-2 zeros TODO finally closed; 5-factor completeness). Tests 241→246.
  Run `28714592528` green; dev probe PASS (linked live-stage rows, unlinked zeros,
  both-different flagged on real RDS); master cleanup 3→0. Commits `2b2de90..74aec5b`.
- **F3b (frontend, local-verified):** Applications tab (live B.5 stages, friendly labels,
  applied dates, graceful empties) · Jobs tab (open roles + REAL Applied badges via
  cross-ref; **no fake Apply** — POST /applications is staff-gated by design, so the
  affordance is honest recruiter guidance; candidate self-apply would be a future backend
  decision) · overview recent rows fixed to the real shape (the old status/updatedAt fields
  never existed server-side). tsc/eslint/build clean; 8-check walk PASS. Frontend-only.

## 2026-07-04 — F4: client-portal deep tabs + admin/employee SLA boards ✅ (local-verified)

Pure frontend slice (no backend change; paths-ignore confirmed — no deploy).

- **Client portal (the external surface):** pipeline page was STILL on the dead pre-B.5
  vocabulary (a D5 remnant F1's employer-kanban fix missed) — rewritten as 7 grouped
  read-only columns (Screening→…→Your Rounds→Offer→Joined) over the real 21 stages;
  **Interviews page created** (endpoint/hook existed since Task 5; the page didn't) + nav;
  Jobs got a truthful role caption. No .ics link faked (the client response doesn't carry
  one; invites arrive by email).
- **Role-conditioning (the thing to get right):** HR (client_admin) renders the offer
  release/joining-date editor; a manager gets an EXPLICITLY-LABELED read-only view — the UI
  never renders a control the backend 403s. Walked end-to-end: manager sees only own jobs,
  manager offer-write → 403, HR release → 200, submissions feedback → 200.
- **Admin/employee:** /employee/queue + /employee/sla + /admin/sla-board on the real SLA
  read-model (KPIs + oldest-first queue). **/admin/employees stays honestly ComingSoon — no
  staff-roster endpoint exists** (backend guard: reported, not faked; needs a small admin
  roster endpoint when wanted).
- **Verified:** tsc/eslint/build clean; 20-check walk PASS (client_admin, client_manager,
  admin; bounce checks included). Two walk-script fixes en route (seeded interview lacked
  client_id — the scoping HID it correctly; bounce check must not follow redirects).

## 2026-07-05 — F5: assessments UI — recruiter surface + admin waiver + the PUBLIC take page ✅

Frontend + one compose tweak. NOTE: the docker-compose.yml change (local-only dummy AWS creds
so presign signing works in the local loop) TRIGGERED the pipeline — paths-ignore covers only
frontend/**. No backend code/migration changed; run `76f4d0c` deployed a content-identical
image, watched to green, /readyz ok. Recorded for the deploy-history's honesty.

- **Recruiter (/employee/assessments):** issue with a ONE-TIME-link modal (raw token shown
  once; server stores only the hash), stage-precondition 409 surfaced cleanly; tests
  dashboard preserving the B.7 honesty guarantee — waived rows show "Waived by admin — no
  score", never a number.
- **Admin (/admin/assessments):** waiver control conditioned on /me/features
  assessment_waiver AND per-row eligibility; flag off → explicit "capability disabled" note,
  read-only table. LEARNED + verified: with the flag OFF the endpoint 404s for EVERYONE
  (probe-proof — it hides its existence; my walk initially expected recruiter-403, wrong);
  flag-on non-admin 403 stays locked by B.8's parametrized boundary tests. The modal
  requires the pass/fail RESULT decision + reason (WaiveIn.result — caught by the walk;
  the first modal version omitted it and 422'd).
- **PUBLIC take page (/take/[token], bare route — no shell/JWT):** 404 generic invalid-link ·
  410 expired/used · 200 frozen paper. **No-answer-leak PROVEN by payload inspection:
  no 'correct' key anywhere; question shape exactly {qid, stem, options}.** 60-min timer,
  auto-submit at 0, double-fire guard, idempotent re-submit shows the stored result.
  **Proctoring = PRESIGN-ONLY** (one wiring call, status chip); the capture loop
  (webcam/face-api/lockdown) stays deferred per B.7 PENDING.
- **Walk findings worth keeping:** options are SHUFFLED per candidate (fixed-index answers
  score ~random — an accidental re-proof of the shuffle); presign 500'd locally on
  NoCredentialsError → compose now carries dummy creds (offline signing needs SOME creds;
  deployed tasks use the ECS role).
- tsc/eslint/build clean; both surfaces + all token semantics walked green. Commit `76f4d0c`.

## 2026-07-05 — F6: CRM board + vendor screens ✅ + F6-E2E full-system regression

### F6 (frontend, local-verified — no deploy)
- **CRM (/employee/crm):** lead board on the B.12 mini-guard vocabulary (new/qualified/proposal/
  negotiation drag + won/lost terminals); Lost opens the reason modal first (422 backstop);
  Convert shows the IDEMPOTENT already-converted state honestly; per-lead activity stream.
- **Vendors (/employer/vendors → Manage):** scorecard KPIs, contracts + validity, the
  vendor×client rate matrix, commission ledger with accrued→paid|void (void needs reason;
  paid/void render NO controls — paid-can't-be-voided mirrored). 17-check walk PASS. Commit
  `d283b7e`.

### F6-E2E regression (verification pass — real HTTP against the local stack + a dev probe)
- **A. Candidate journey (28 legs): 27 PASS · 1 ENV-LIMIT · 0 FAIL.** The full sourcing→
  aptitude(take/auto-grade)→internal R2→RTR gate→submit→offer→joined→placement (fee = annual
  CTC × client 12% = 120,000, exact)→guarantee, PLUS breach→reopen, replacement→no-double-fee,
  vendor commission at client rate, credit-note→auto-void, dedup→merge→linkage-conflict-flag,
  CRM convert, notification enqueue→sweep→sent, erasure→search_doc/bidx/resume nulled. The one
  ENV-LIMIT: invoice PDF→S3 500s locally (dummy creds; dev-proven in B.9).
- **B. Gate matrix (26 legs): 24 PASS · 2 FAIL.** Founder gates, /transition, /waive-404-when-off,
  /take token surface, admin/client/employee gates, tenant isolation, idempotency, error
  envelope — all correct. **TWO FAILS = one real security bug (below).**
- **C. Frontend↔backend:** every F1–F6 surface calls the real endpoint + renders real 409/403/
  404/empty. NO fourth dead-vocabulary remnant; NO mocks.
- **D. Cross-slice hooks:** all verified green inside Part A (credit-note→void, merge→conflict+
  repoint, assessment/waiver single-fire, breach→reopen, convert→job-via-normal-path,
  erasure→null).
- **E. Integrity (on dev RDS as sps_app):** head 0032, ALL dev stage values in B.5 vocabulary,
  append-only REVOKE HOLDS (DELETE denied on audit_logs/consents/candidate_timeline).

#### 🔴 E2E FINDING — E2E-1 (real bug, own slice): broken access control on 5 staffing GETs
`GET /api/{candidates, clients, jobs, jobs/{id}/pipeline, client-portal/overview}` in
`staffing.py` are **authenticated-only — no `_require_staff`**. PROVEN: a candidate session
reads another candidate's PII (name/email/skills) via GET /api/candidates (200 + leaked row).
Tenant-scoped so NOT cross-tenant, but a candidate/client sees other candidates/clients/jobs
WITHIN their tenant. The B.5-fix route-smoke matrix only checked no-500, not gates — so it never
caught this; `job_pipeline`/`employer_overview` got their NameError fixed there but never had a
gate. **Fix = add `_require_staff` to all 5 + extend the smoke matrix to assert candidate/client
sessions get 403 on staff GETs. Backend micro-slice (E2E-1), STOP-1-exempt, its own deploy —
NOT folded into F6.** Triage: real, security-severity, but low blast radius on dev (little data).

## 2026-07-05 — E2E-1: access-control fix + the route-smoke matrix repaired ✅ (deployed + dev proof)

Backend micro-slice from the F6-E2E finding (no migration, head 0032).

- **THE FIX:** `_require_staff(ctx)` added to the 5 ungated staffing GETs
  (`/candidates`, `/clients`, `/jobs`, `/jobs/{id}/pipeline`, `/client-portal/overview`). A
  full-class grep confirmed EXACTLY these 5: `employee/overview` has an equivalent inline gate;
  the 4 privacy GET/POSTs are candidate-self (self-scoped to `ctx.user_id`), correct. No sixth.
- **THE DEEPER FINDING (why E2E-1 escaped): the B.5-fix route-smoke matrix was a SILENT NO-OP
  since it shipped.** `app.include_router` wraps every router in an opaque `_IncludedRouter`
  (custom routing layer), so `isinstance(r, APIRoute)` over `app.routes` matched ONLY
  /healthz+/readyz — **60 real /api GETs went untested every run.** The "found no other latent
  500s" in B.5-fix was vacuously true. Fixed `_get_routes()` to enumerate from `app.openapi()`
  (canonical, wrapper-immune) and added `_ROUTE_FLOOR >= 40` assertions to BOTH matrices so a
  future collapse to no-op fails the test.
- **THE CLASS-GUARD (fail-closed, PROVEN):** the new gate-matrix asserts every /api GET not on
  an explicit non-staff allowlist (auth/me/privacy/client/take/register) returns 403 to a
  candidate AND a client session; a 2xx is a flagged leak. Demonstrated fail-closed: removing a
  gate made it fail with `/api/candidates [candidate] → 200`. A NEW ungated staff GET fails by
  default. This is the SECOND class-guard added from a found regression — and this time the
  guard itself had to be repaired to actually run.
- **Deploy + proof:** 247 tests green (246 + gate-matrix); commit `3964fcd` → pipeline
  `28728495905` green (migrate no-op, head 0032) → dev real-op as sps_app: all 5 return
  candidate 403 / client 403 / staff-passes-gate on real RDS (were 200 for all pre-fix) — PASS
  exit 0; unauth still 401.
- **Process note:** the local suite briefly went red mid-slice because an over-aggressive debug
  sweep deleted the UNCODIFIED local seed question bank (12 questions) the assessment tests
  depend on — not a code break; reseeded (12 neutral-text active questions). Flags a real gap:
  the aptitude seed bank isn't reproducible from the repo (no conftest/seed script) — logged.

## 2026-07-05 — E2E-3: aptitude seed bank made reproducible (test-infra) ✅

Test-only slice (`backend/tests/conftest.py`). No app/migration/engine change; the deployed
image is content-identical (CI run `28729671425` green — which also validates the fixture in a
fresh CI DB).

- **THE PROBLEM:** `test_assessments` assumed a persistent 12-question bank. Migration 0026
  DOES data-seed a SAMPLE bank, so a freshly-*migrated* clone has it — but it's ordinary DML a
  sweep deletes permanently, with nothing to recreate it (exactly how the suite broke mid-E2E-1).
  A suite that only passes on uncodified DB state isn't truly reproducible.
- **THE FIX:** a session-scoped autouse fixture guarantees EXACTLY 12 active neutral-text
  questions for SPS001 independent of DB state — it deactivates any pre-existing active
  questions, installs a deterministic fixture bank, and restores the prior state on teardown.
  Decoupled from the migration seed on purpose (tests depend on the fixture, not on whatever is
  or isn't in the DB).
- **PROVEN:** wiped ALL questions to simulate a fresh clone → `test_assessments` 24 passed from
  empty; full suite 247 green; teardown leaves 0 orphaned rows.
- **LESSON:** a green suite that silently depends on uncodified local state is a reproducibility
  trap — it hides until a fresh clone or a second environment (staging) exists. Worth an audit
  for other tests that assume seeded data before staging stands up.

## 2026-07-05 — F7: notification center + founder trend charts ✅ (frontend backlog CLOSED)

Last frontend-backlog slice. Frontend-only (no deploy; recharts was already a dep — no new package).

- **Notification center (/admin/notifications):** read-only view of the B.10 LEDGER
  (template/channel/recipient/status/attempts/last_error/time + status filters). Honest delivery
  labeling: a banner states it's a ledger not a mailbox; console 'sent' = 'logged to console (dev
  sink)', never 'delivered'; a still-pending row on an unregistered channel shows 'awaiting
  channel (Part D) — parked'. **Correctness caught mid-build:** 'parked' is NOT a status
  (ck_notifications_status = pending/sent/failed/skipped) — the parked state is DERIVED from
  pending + unregistered channel, not a fake status value. Real DELIVERY is Part D.
- **Founder trend charts (extends the F1 KPI strip):** trends line (revenue/placements/
  applications, 6-month) + by-BU bars with Academy/Consulting rendering honestly zero (real
  queries). Owner-gated by the SAME probe pattern as F1's FounderKpiStrip — a plain admin's 403
  resolves the section to null; the page never breaks. B.11's 5-min cache is a feature (?refresh
  busts).
- **Verified:** tsc/eslint/build clean; owner+admin walk PASS (ledger honesty, owner charts,
  admin graceful-403, by-bu honest zeros, refresh). Walk artifacts worth noting: two seed bugs
  (rendered_body NOT NULL; the 'parked' status CHECK violation that surfaced the derived-state
  correction) and a founder-cache stale-zero (cleared with ?refresh=1) — all harness, not code.
- **THE F-SERIES (F1–F7) IS COMPLETE.** The staffing frontend backlog is closed: marketing→
  login→role routing, all role dashboards, the recruiter pipeline (optimistic-locked), candidate
  tabs, client-portal deep tabs, admin/SLA screens, assessments UI + public take page, CRM board,
  vendor depth, notification center, founder charts. Deferred (unchanged): proctoring capture
  loop, real notification delivery (Part-D channels), hosting (C1/D.6), E2E-2 (client.fee_percent
  write API), the EdTech vertical.

## 2026-07-05 — A1: Academy foundation (EdTech vertical begins) ✅ (deployed + real-op proof)

First slice of the Academy vertical (EdTech plan v2 §4). STOP-1-approved big migration.

- **Migration 0033 — the whole `academy` schema (9 tables):** courses/cohorts/students/
  enrollments/attendance/assignments/assignment_submissions/certificates/payments. Two-axis
  tagged (business_unit_id='ACADEMY'), soft-delete, TwoAxisMixin (updated_at included uniformly).
  CHECKs per the plan (cohort mode/status, enrollment status/payment_status, payment status).
  Within-schema refs = real FKs; cross-schema (trainer_id, students.user_id, graded_by,
  enrollments.application_id) = SOFT-REFS (no FK, matching jobs.owner_user_id/candidates.user_id).
- **Student PII = the candidate treatment:** phone_enc/pan_enc (bytea AES-256-GCM) + phone_bidx/
  pan_bidx (HMAC blind index) + CITEXT email + tsvector; UNIQUE(tenant,email) +
  UNIQUE(tenant,phone_bidx) dedup. Proven on dev: sps_app inserted a student, ciphertext at
  rest, decrypts on access.
- **Student↔login reuses F3a exactly:** students.user_id soft-ref + ix_students_user_id (A3
  auto-links at registration; column + docstring land now). Test asserts no FK on user_id.
- **FEATURE_ACADEMY (default OFF):** /api/academy/* 404s when off (probe-proof, like AI/waiver);
  A1 ships only the gate + /ping. Test-locked 404-off / 200-on.
- **8-course seed, reproducible from the repo (E2E-3 lesson):** app/academy_seed.py::seed_courses
  is the single source of truth (idempotent), called by BOTH migration 0033 and the test
  fixture — no uncodified seed state. Default fee ₹50,000, placeholder content, is_published=
  false (A2 publishes). Titles: .NET FS, AI/ML, Python, Data Analyst, Data Engineer, Cloud,
  Java FS, Angular/React.
- **Grants:** academy tables are normal-DML — NOT in the append-only REVOKE list; the bootstrap's
  ALTER DEFAULT PRIVILEGES IN SCHEMA academy auto-granted sps_app DML on the migrate-created
  tables (proven by the probe's successful student INSERT — no bootstrap re-run needed).
- **Tests 247 → 252.** Deploy: commits `860ad59..03b6f18` → pipeline `28730935120`/`28731124911`
  green (migrate 0033 exit 0, seed applied) → dev probe as sps_app: 9 tables ✅, 8 courses at
  ₹50k ✅, encrypted-PII round-trip ✅ — PASS exit 0. /readyz ok.

## 2026-07-05 — A2: Academy course catalog + public listing ✅ (deployed + real-op proof)

Second academy slice. NO MIGRATION — the 0033 tables cover it (head stays 0033).

- **Staff catalog (FEATURE_ACADEMY + _require_staff, tenant+ACADEMY scoped, idempotent, audited):**
  course create/patch/list(incl. unpublished)/get; the publish toggle (is_published +
  status='active'); minimal cohort create/list. Slug auto-derived or validated; duplicate slug
  409; title accepts dots/slashes/parens (real course names like '.NET Full-Stack').
- **PUBLIC surface (unauthenticated, marketing-facing) — the leak-nothing guarantees, each
  structural:** `GET /api/academy/public/courses` + `/{slug}`. (a) PUBLISHED-ONLY — WHERE
  is_published=true AND status='active' AND not-deleted → no draft ever leaks; (b) SAFE-FIELDS-
  ONLY — `_public_course_dict` is an explicit allowlist (title/slug/description/syllabus/level/
  duration/fee/currency/next_cohort_start), NO id/tenant/status/is_published/timestamps, and
  courses carry no PII; (c) TENANT-BY-HOST — resolved like public registration, so a subdomain
  sees only its own catalog. Also flag-gated via `is_enabled` (no ctx) so the whole vertical is
  probe-proof even unauthenticated (dev smoke: flag-off live service → 404).
- **NEW PUBLIC ENDPOINT — noted for A10:** `/api/academy/public/` added to the route-smoke
  gate-matrix's non-staff allowlist (legitimately unauthenticated; A10 extends the matrix to
  academy).
- **Tests 252 → 257.** Manual walk PASS (publish→appears-safe-fields→unpublish→gone). Deploy:
  commits `3cae384..64a4a10` → pipeline `28731650555` green → dev probe as sps_app (flag flipped
  in-process; deployed service stays OFF): seeded course invisible until published → published
  shows safe-fields-only → fresh draft doesn't leak → unpublish→gone — PASS exit 0, self-cleaned.
  Live service (flag off) public route → 404; /readyz ok.

## 2026-07-05 — A3: Academy student registration + SEPARATE student auth ✅ (deployed + real-op proof)

Third academy slice — the most privilege-sensitive: a SECOND auth system. STOP-0 (identity) +
STOP-1 (migration) both approved.

- **Identity (Option 1, approved):** academy students are a DISTINCT identity in
  `academy.students` with their OWN argon2 `password_hash` — **NO `shared.users` row** for a
  student; the staffing identity spine is untouched. Email is reusable across the boundary
  (different tables). `students.user_id` stays null (bridge-only, not auth).
- **The two-auth separation (the security core), built with BOTH your conditions:**
  - **Distinct cookie** `academy_access_token` (staffing = `access_token`) — a dual-identity
    browser holds both without collision; each resolver reads only its own.
  - **Distinct signing secret** `jwt_academy_secret` + distinct `type=academy_access` +
    `kind=academy_student` claim. An academy token **cryptographically fails** verification in
    the staffing decoder and vice-versa — fail-closed even if a `kind` check were forgotten.
  - **Separate resolver** `get_current_student` (never a branch of the UNCHANGED
    `get_current_context`) — a staff endpoint structurally cannot accept a student token.
  - `/api/academy/auth/{login,me,logout}` authenticate against `academy.students` (argon2);
    neither auth path authenticates the other's identity.
- **Containment PROVEN both directions, incl. the dual-identity person** (same email, staffing
  candidate + academy student): academy token bounced from all staff surfaces; staffing token
  bounced from academy-student surfaces; dual-holder correct per cookie. The E2E-1 gate-matrix
  extended (fail-closed) with `/api/academy/auth/` + `/register/`.
- **Consent = Option A (approved):** student DPDP consent in the canonical `shared.consents`
  ledger via a NEW `subject_student_id` soft-ref (uuid, no cross-schema FK, mirroring
  `subject_candidate_id`); one-subject CHECK widened to `num_nonnulls(user,candidate,student)=1`.
  Guardian consent on the student row + audit. **This touched `shared.consents` (NOT
  `shared.users`).**
- **Registration:** one all-or-nothing txn — captcha (test-mode) → under-18 guardian gate (422
  without) → consent → tenant-from-Host → academy dedup (email OR student_id → 409) →
  `academy.students` (argon2 + encrypted phone + identity + confirmed ID-card via B.1
  presign/head_object) + `shared.consents` row + audit → 2 B.10 emails (ConsoleChannel dev,
  SES = Part-D). Password argon2, never plaintext. POLICY_VERSION bumped; consent notice
  `[FOUNDER DRAFT]`. ID-card private S3, deleted by `anonymize_student` (student DPDP trigger =
  later slice).
- **Migration 0034** (revision id kept ≤32 chars — `alembic_version` is varchar(32)):
  `academy.students` credential/identity/id-card/guardian columns + `shared.consents`
  subject_student_id. up→down→up clean. Not in REVOKE list. **Tests 257 → 264.** Deploy:
  commits `9a26dce..` → pipeline `28736511541` green (migrate 0034 exit 0). Dev probe as sps_app
  (flag flipped in-process; deployed service stays OFF): (1) registered — academy.students row
  (argon2 + encrypted PII + real id_card S3 object) + shared.consents row + NO shared.users row
  ✅; (2) CONTAINMENT both directions — academy token rejected by the staffing decoder AND
  vice-versa (distinct secret + type) ✅; (3) erasure scrubbed the student + deleted the id_card
  S3 object ✅ — PASS exit 0, self-cleaned. Flag-off live service: academy auth/register → 404;
  /readyz ok.

## 2026-07-05 — A4 Part 1: staffing.tests generalized vertical-agnostic (migration 0035) ✅

The one migration A4 forces (STOP-1 approved). Identity/discriminator ONLY — the 60Q/60min
engine extension + academy bank + issue endpoint are the following A4 prompts.

- **0035:** `staffing.tests` `application_id`/`candidate_id` → NULLABLE (keep within-schema FKs);
  add `enrollment_id` + `student_id` soft-refs (no cross-schema FK, per convention); add
  `ck_tests_one_identity` — EXACTLY ONE pairing set: staffing (application+candidate) OR academy
  (enrollment+student); index the two new columns. NO FORK (reuse mandate): the take flow
  (`/take/{token}`) stays identity-agnostic; only issue + the post-grade callback branch on
  `business_unit_id`. NO backfill (0 existing rows violate the CHECK — all are staffing rows).
  up→down→up clean. Not in the REVOKE list.
- **Class-guard test** (`test_tests_identity_check.py`): the CHECK is now a permanent DB guard
  (route-smoke discipline) — academy pairing inserts; mixed/half/all-null rows → IntegrityError.
  Suite 264 → **265**.
- **⚠️ A4-P2 CARRY-FORWARD (do NOT act until A4-P2):** `ck_tests_one_identity` guarantees
  exactly-one-pairing but does NOT tie the pairing to `business_unit_id`. A row could carry
  `business_unit_id=ACADEMY` with the STAFFING pairing and the CHECK wouldn't catch it — and the
  post-grade callback branches on `business_unit_id`. **A4-P2 must enforce BU↔pairing consistency
  at the ACADEMY issue path (service-layer assertion + targeted test), NOT as a DB CHECK** — a
  BU-coupled CHECK would hardcode the BU axis value into the constraint (brittle). Keep the
  invariant where the writer is.

## 2026-07-05 — A4 Part 2: aptitude engine extension (60Q) + academy bank + admin-triggered issue ✅

Reuse mandate honored — the B.7 engine extended ONCE at the issue seam; no academy.tests fork.

- **Engine seam (the only generic change):** `select_bank_paper(db, tenant_id, business_unit_id,
  count)` — threads BU + count; `freeze_paper`/`select_questions`/`grade` signatures untouched.
  The BU filter also ISOLATES verticals (academy questions never leak into a staffing paper).
  Staffing issue now calls it with `('STAFFING', 30)` — result-preserving (the staffing bank is
  STAFFING-BU); the 24 staffing-assessment tests + the 0035 guard stay green.
- **Academy bank (migration 0036, data-only):** course-INDEPENDENT aptitude/reasoning/verbal/
  english bank, 60 active `[SAMPLE]` questions, seeded via the idempotent
  `app.academy_seed.seed_aptitude_bank` (shared source of truth: migration + conftest fixture,
  E2E-3 reproducibility). **Minimum to draw a 60Q paper = 60. CARRY-FORWARD:** a PRODUCTION bank
  must be a pool MUCH larger than 60 for question-level paper variety / anti-leak — with exactly
  60, papers differ only by option-shuffle; `[SAMPLE]` is a dev placeholder, real = `[YOUR CONTENT]`.
- **Admin-triggered issue:** `POST /api/academy/enrollments/{id}/aptitude/issue` (admin-gated,
  FEATURE_ACADEMY, `applied`-precondition), draws 60 from the academy bank, one-time token,
  writes the ACADEMY identity pairing (enrollment+student, staffing refs null). Candidate → 403
  (can't self-issue, decision 8); flag off → 404.
- **BU↔pairing invariant (0035 carry-forward):** enforced at the WRITER as a RAISED domain error
  (`_require_academy_pairing` → 409 BU_PAIRING_INVARIANT, canonical envelope) — NOT a bare assert
  (which would 500 + be stripped under `python -O`). This also **RESOLVES the null-student_id
  carry-forward** (the same guard rejects a null student_id with the envelope, not a raw
  IntegrityError from ck_tests_one_identity) — folded here since it's the same invalid state.
- **Take + post-grade branch:** `/take/{token}` unchanged; the callback branches on
  `business_unit_id`: ACADEMY → stamp `enrollment.aptitude_score = correct/60×100` + `applied→
  tested` (pricing = A5); STAFFING → the existing pipeline path (untouched). No-answer-leak
  preserved. **Grade arithmetic verified at a non-trivial value:** 45/60 → 75.0 (A5's 75/85/95
  discount boundaries stand on this).
- The E2E-3 staffing seed fixture was scoped to `business_unit_id='STAFFING'` so it no longer
  clobbers the academy bank (the issue path is BU-scoped now). **Tests 265 → 272.**

## 2026-07-05 — A5: tiered discount + enrolment pricing (the money-logic slice) ✅

No schema migration (A1 already has enrollments.discount_percent + final_fee); only a DATA-only
migration 0037 (the payment-link notification template).

- **`resolve_discount_percent` (pure, C.2-locked, inclusive-lower):** ≥95→20 | 85–<95→15 |
  75–<85→10 | <75→0. `<75` is FULL PRICE, NOT a gate (decision 5) — returns 0, enrolment still
  proceeds. Clean property: boundaries fall on EXACT integer correct-counts (57/51/45 of 60), no
  rounding ambiguity.
- **`final_fee = course.fee × (100−discount)/100`**, READ off the course row (per-course
  configurable, never hardcoded 50000), rounded via the SAME `round(float,2)` convention as the
  B.9 invoice fee. PRE-TAX — **GST/TDS stay INERT** (final_fee == pre-tax discounted fee exactly).
  Discount stamps as a PRICE (decision 4): only discount_percent + final_fee on the enrollment;
  no coupon entity.
- **Post-grade callback (extends A4's academy branch):** stamps discount + final_fee, enqueues
  the payment-link email, advances **applied→tested→offered in ONE grade** — see DECISIONS
  (2026-07-05): a graded academy enrolment RESTS at `offered`, `tested` is transient. **This
  supersedes A4's "ends at tested"** (A4 assertions + probe updated).
- **Payment-link email (STUB):** new `academy_payment_link` template ([FOUNDER DRAFT]), to the
  student, carrying course + discount % + final_fee + a clearly-marked stub link
  `[STUB — A6/Part-D] /academy/pay/{enrollment_id}` (drop-in shape for A6's real Razorpay link).
  B.10 ledger + ConsoleChannel (SES = Part-D). Idempotent on the graded ATTEMPT (test id): a
  re-grade can't double-send; a fresh retake re-prices + re-sends.
- **Migration 0037 (DATA-only, no schema change):** seeds the template via the idempotent
  seed_notification_templates. up→down→up clean. **Tests 272 → 298.**

## 2026-07-05 — A6: payment activation (STUB, per the founder's STUB/PAID map) ✅

Idempotent activation is the property this slice lives on. NOT a gateway decision — Razorpay is
PAID→STUB in dev per the founder's map; Part-D swaps in the real order+HMAC webhook as a DROP-IN.

- **Schema (STOP-1 approved, migration 0038):** `academy.payments` gains `paid_at` +
  `receipt_s3_key` (both nullable, no backfill). The A1 payments table (amount/status/provider/
  provider_ref) was reused unchanged. Migration 0039 (DATA-only) seeds the
  `academy_enrolment_active` template.
- **The single activation seam (`_activate_payment`):** the stub confirm AND the future
  HMAC-verified Razorpay webhook BOTH enter it — marks paid + paid_at, activates the enrolment
  (offered→active), renders the receipt PDF via the existing ReportLab+S3 seam, enqueues the
  confirmation email. **Part-D adds signature-verify + order-lookup BEFORE this call and changes
  NOTHING after it** (provider_ref holds the Razorpay payment id; stub uses `stub-<uuid>`).
- **Amount is READ off `enrollment.final_fee`** (C.2) — never recomputed, never hardcoded.
  Pre-tax; GST/TDS stay inert (no tax added at payment).
- **Idempotency/guards (keyed on the PAYMENT ROW's own status, never the enrolment):**
  (1) this payment already paid → no-op success (webhook REDELIVERY); (2) else the enrolment
  must be at `offered` to activate — NOT offered (tested, or already-active via a DIFFERENT
  payment) → 409 conflict, fail-closed (a distinct unpaid payment vs an active enrolment is a
  real two-payments conflict, never swallowed). `_create_or_get_payment` refuses to mint a
  second payable row against an active/paid enrolment (409 ENROLLMENT_NOT_PAYABLE).
- **Consumes the A5 decision:** `offered` = "awaiting payment" → payment activates it to
  `active`. The stub confirm is `POST /api/academy/enrollments/{id}/pay` (matches A5's stub link).
- **Tests 298 → 306** (8 A6: amount-reads-final-fee, create-idempotency, happy path w/ receipt +
  email, DOUBLE-CONFIRM redelivery no-op, wrong-state 409, SECOND-PAYMENT conflict 409,
  create-against-active 409, no-tax). moto S3 for the receipt PDF.

## 2026-07-05 — FE#1: public academy storefront (course listing + detail) ✅ (local-verified)

Frontend only, local-verified — the frontend has no deploy target (C1). Two net-new pages in
the (marketing) route group consuming the A2 public endpoints. commit `891914e`.

- **/academy** (published-course grid) + **/academy/courses/{slug}** (detail) — built from the
  F1 marketing design tokens (education gold accent, max-w-7xl, rounded-2xl cards) + the lib/api
  client; loading/error/empty/404 states; fee formatted from the row's OWN currency (no hardcoded
  number). Public = no auth (backend enforces published-only / safe-fields / tenant-by-Host).
  APPLY routes to /academy/register?course={slug}.

## 2026-07-05 — FE#2: public academy student registration + the local-S3 (MinIO) infra it required ✅

Frontend register page (commit `7b5d08a`) + the local-S3 infra its ID-card upload needed (MinIO,
commit `ba0bff1` — see its own entry below). Local-verified.

- **/academy/register** (reads ?course=) consuming GET /register/config, POST /register/id-card/
  presign, POST /register/student. Full form + client validation mirroring the backend, under-18
  guardian gate, DPDP consent (the real FOUNDER-DRAFT notice from config), dev captcha stub, and
  college-ID upload via presign→PUT→submit. **The id-card upload can't complete locally without
  working S3** — which is why FE#2 pulled in the MinIO infra (ba0bff1). On success routes to
  /academy/login (built in FE#3).

## 2026-07-05 — FE#3: academy student login + student portal shell (A3 two-auth) ✅ (local-verified)

The one net-new AUTH surface — wires the A3 academy cookie + the middleware that reads it.
commit `3853c91`.

- **/academy/login** sets the SEPARATE academy_access_token cookie (distinct secret from staff);
  a (student) route-group portal shell at **/academy/student** (its own layout, calls /auth/me so
  the session is proven to HOLD across reload/deep-link, not just the post-login redirect).
- **Two-auth containment PROVEN BOTH DIRECTIONS** (the security property): middleware gates
  /academy/student/* by the academy cookie via readAcademySessionFromCookie (requires
  kind=academy_student); a staff access_token → bounced (307 → /academy/login); a student cookie
  → bounced from /admin (307); the distinct backend secret rejects a staff token at
  /academy/auth/me (401). Reload holds (SameSite=lax, Path=/, no Secure over http). Reuses the F1
  /login POST + home-routing pattern.

## 2026-07-05 — Local S3 (MinIO) for frontend bring-up — dev/prod inert (infra, local-only)

Local-only infra so the presign→browser-PUT→confirm flow (ID-card upload, receipts) works
locally. NOT a deployment change.

- **MinIO** added to docker-compose (`:9000` API, `:9001` console); backend wired via
  `S3_ENDPOINT_URL` (backend→MinIO) + `S3_PUBLIC_ENDPOINT_URL` (browser-reachable presign host);
  local bucket created idempotently by `seed_local_academy.py`, same NAME as dev so keys match;
  browser CORS opened to `http://localhost:3000`.
- **INVARIANT (documented so it's re-verifiable, not tribal):** presign now uses a SEPARATE
  public-endpoint client (`storage._presign_client()`, distinct from `_client()`); dev/prod
  behaviour is gated on BOTH `S3_ENDPOINT_URL` and `S3_PUBLIC_ENDPOINT_URL` being UNSET — proven
  inert: with both empty, `_client()` AND `_presign_client()` construct byte-identical to the
  prior bare `boto3.client("s3", region_name=...)`, and `presign_put`/`presign_get` still emit
  virtual-host real-S3 SigV4 URLs (`https://<bucket>.s3.amazonaws.com/…`) — dev/prod presigned
  URLs unchanged. KMS is a dev/prod bucket-default (no SSE in app code) → locally absent (no-op),
  dev/prod untouched. Re-verify by clearing the two envs and asserting the presign output shape.
- Test-robustness (CI unaffected — CI runs with the overrides unset + academy flag off): a
  conftest autouse fixture clears the S3 endpoint per-test (tests use moto, never MinIO); the
  route-smoke matrix allowlists the no-data `/api/academy/ping` diagnostic (visible only because
  local runs the academy flag ON). Suite 306 green on a clean DB.

## 2026-07-05 — FE#4: student-facing enrolments read (backend) + take wiring

- **`GET /api/academy/students/me/enrollments`** (get_current_student-gated, no schema change):
  the student's OWN enrolments (course/status/aptitude_score/discount/final_fee/payment_status
  + `active_test` presence). STRICT SCOPING — derived from the SESSION only, NO student_id/
  enrollment_id param, so student A has no request shape to read B. NO answer leak (no served
  questions/answers/token). Cross-student isolation + gate(401) + no-leak + active-test lifecycle
  tested. Local-only until the backend track next pushes.
- **CONSTRAINT surfaced:** the take LINK cannot be returned by a student endpoint — B.7 stores
  only the SHA-256 of the one-time token (raw token shown once at issue, never stored). So
  `active_test` is a presence indicator (valid_until, attempt_no); delivering the actual
  `/take/{token}` link to the student needs an aptitude-invite notification at issue time (the
  "stubbed hop as a notification row" pattern) — a follow-up decision.
- **CARRY-FORWARD (record, do NOT fix now):** the take API `GET /take/{token}` returns
  `time_limit_minutes = settings.test_time_limit_minutes` (the STAFFING config) regardless of the
  test's business_unit. It's coincidentally also 60 min, so academy renders correctly today —
  but the academy time-limit is accidentally coupled to staffing's value. Branch it on
  business_unit_id eventually. Latent coupling, not blocking.

## 2026-07-05 — FE#4b: aptitude-invite notification (take link reaches the student in-app)

- At `POST /enrollments/{id}/aptitude/issue`, enqueue `academy_aptitude_invite` to the student
  (`vars.take_link = /take/{raw_token}`, captured at the one moment the raw token exists),
  idempotent on the test (`academy:aptitude_invite:{test.id}`). New read
  `GET /api/academy/students/me/notifications` (get_current_student-gated) returns the student's
  own academy notifications with `take_link`. "My Academy" links the "Take aptitude test" button
  to the take link pulled from the student's OWN invite. Migration 0040 (data-only) seeds the
  template. Cross-student notification isolation + gate + idempotent-on-test + enrolments-stay-
  tokenless tested. **Suite 311 → 316.** RETAKE verified: fail → re-issue = a NEW test = a NEW
  token = a SECOND invite (not suppressed by the prior key).
- **CARRY-FORWARD (latent inconsistency — record, do NOT fix now):** the two student-facing reads
  key on DIFFERENT session identities — `/students/me/enrollments` scopes on
  `StudentContext.student_id`, `/students/me/notifications` scopes on
  `recipient == session email` (+ `business_unit_id='ACADEMY'`). Correct TODAY (academy email is
  unique per tenant, and the BU filter excludes staff notifications sharing an email). But the
  divergence is HISTORICAL, not intentional: notifications key on email because the Notification
  row has no student_id column. If email-uniqueness ever weakens, or a student changes their
  email (past notifications keep the old recipient), the notification read should move to a
  student_id linkage to match the enrolments read. A latent inconsistency to note, not fix.

## 2026-07-05 — Reconciliation push (FE#1–#4b) ✅

FE#1–#4b pushed to develop; dev at head **0040**; Phase-3 dev probe GREEN on real RDS — staffing
S3 round-trip inert with the presign-split deployed (envs unset), the academy issue→invite→
notification-read(with take_link)→take→submit→enrolments-reflect chain, and cross-student token
isolation (B cannot read A's notification or A's live take token). FEATURE_ACADEMY confirmed
back OFF on the live service (register/config + students/me/enrollments both 404).

## 2026-07-05 — FE#5: result / discount view + course.fee surfaced in /me/enrollments ✅

Result panel in the (student) portal for a graded enrolment (offered/active/completed): score →
earned tier → list→discount→final, all the backend's numbers (never recomputed). <75 = FULL
PRICE framed as the student's price, NOT a failure/gate (decision 5). "Proceed to payment" CTA →
/academy/student/pay?enrollment={id} (404s until #6). **Backend: `course.fee` (the existing list
fee, already public on the storefront) added to the GET /students/me/enrollments serializer so the
"you saved X" line has list + final — NO new column, NO migration (dev stays head 0040). Isolation
unchanged (the field addition didn't touch session-scoping — re-confirmed on dev).** Local <75 seed
fixture (Farah, 60%→0%) added for the walk.

## 2026-07-06 — FE#6 backend: student-INITIATE pay endpoint (shares _activate_payment with the A6 staff confirm) ✅

- **`POST /api/academy/students/me/enrollments/{id}/pay`** — get_current_student-gated (academy
  cookie only). STRICT SCOPING: the enrolment is resolved as the STUDENT'S OWN (session
  student_id) — a student can pay ONLY their own enrolment; NO param by which A pays B's (B's row
  won't match A's session → 404, fail closed). Money makes this isolation load-bearing (A paying
  B's enrolment would activate someone else's row).
- **Shared seam:** calls the SAME `_activate_payment` the A6 staff webhook-confirm uses —
  idempotency (`academy:payment_confirmed:{pay.id}`, redelivery no-op), offered→active, receipt
  PDF, and email all UNCHANGED; the ONLY differences are auth + this INITIATE trigger. Proven by
  a test asserting both paths produce the identical activation effect.
- **Two-endpoint split is INTENTIONAL (Part-D):** this student endpoint is the INITIATE seam →
  in Part-D it becomes "create Razorpay order"; the A6 staff `POST /enrollments/{id}/pay` stays
  the HMAC-verified webhook CONFIRM (server-to-server); `_activate_payment` is what both share and
  neither changes. The A6 staff endpoint is UNCHANGED (pure append, 0 deletions).
- NO migration (endpoint on existing tables; dev stays head 0040). Tests 316 → 321 (isolation +
  happy/redelivery + wrong-state 409 + gate 401 + shared-seam). Dev-probed on real RDS.

## 2026-07-06 — FE#6 frontend: pay confirmation page (onto the student-initiate endpoint) ✅ (local-verified)

Frontend only, local-verified (no deploy target, C1). Pay page at /academy/student/pay?enrollment={id}
in the (student) shell, onto POST /academy/students/me/enrollments/{id}/pay. The risk is the
frontend's handling of a state-changing money-adjacent call:
- **IN-FLIGHT GUARD (load-bearing):** a `useRef(false)` flag checked + set SYNCHRONOUSLY before the
  awaited POST (cleared in finally) — a double/impatient click fires EXACTLY ONE POST (proven
  headless: the identical control-flow → 1 POST; not relying on backend idempotency as the only
  defense). `disabled` is the secondary/visual guard.
- **NETWORK-UNKNOWN:** a non-ApiError throw (lost response) → "Confirming your payment…" → re-check
  /me/enrollments for server truth; never says "failed", never silently re-POSTs.
- **409 mapping:** STATUS_INVALID → reconcile (if actually active → enrolled) else a distinct
  "not awaiting payment" message — not a generic toast.
- **Load-gated:** offered → pay CTA · active/paid → enrolled + receipt (no CTA) · applied/tested →
  "nothing due". Receipt fetched FRESH per download (POST /pay idempotent → fresh presigned URL,
  handling the ~5-min TTL). Honestly labelled a dev/STUB payment (Razorpay = Part-D).

The academy student happy path is now walkable end-to-end locally: storefront → register → login →
My Academy → take → result/discount → pay → enrolled + receipt.

## 2026-07-06 — FE#7 (B) backend: durable receipt read + has_receipt signal ✅

- **`GET /api/academy/students/me/enrollments/{id}/receipt`** — get_current_student-gated,
  own-scoped (session student_id). Resolves the paid payment (enrollment_id + status=='paid' +
  receipt_s3_key non-null), returns a FRESH presigned URL via `storage.presign_get` reused
  verbatim (the MinIO-split-aware seam; ~5-min TTL). Failure shapes: not-yours/nonexistent →
  404 NOT_FOUND (indistinguishable — the isolation property, a presigned PII-document link);
  own-but-unpaid/no-receipt → 404 RECEIPT_NOT_AVAILABLE (reachable only after ownership,
  leaks nothing cross-student).
- **`has_receipt: bool` added to /me/enrollments** — EXISTS(paid payment WITH receipt_s3_key
  non-null), NOT payment_status=='paid'. The precise "there is a fetchable receipt" signal: the
  seeded direct-insert paid row (receipt_s3_key null) and Part-D paid-before-receipt windows are
  paid-without-receipt, so the dashboard gates "Download receipt" on has_receipt and never
  promises a receipt that 404s.
- NO migration (computed from the existing Payment row; dev stays head 0040). +36 lines to
  academy.py, 0 deletions. Cross-student isolation + wrong-state (both 404s) + has_receipt-true-
  vs-false + gate tested (5). Suite 321 → 326. Dev-probed on real RDS through the real S3 presign
  seam (first time the receipt read hits real S3 — local was MinIO).

## 2026-07-06 — FE#7 (B) frontend: student dashboard — has_receipt-gated receipt download ✅ (local-verified)

Frontend only, local-verified (no deploy target, C1). Enhanced "My Academy" (the all-states
enrolment list from #4/#5) with the paid/receipt block on a graded enrolment: payment_status!=paid
→ "Proceed to payment" (#5); paid → "✓ Paid — you're enrolled" + a **"Download receipt" button
ONLY where has_receipt is true** (never gated on payment_status — a paid-but-no-receipt row, the
seed shortcut / Part-D pending window, shows NO button, so the button never promises a receipt
that 404s). Download → GET …/receipt → opens a FRESH presigned URL each click (5-min TTL never
stale). Errors: RECEIPT_NOT_AVAILABLE → "receipt isn't ready yet" (clean, per-card); 401 →
re-login; never a raw error. Verified: seeded active (paid, receipt_s3_key null) → no button; a
real #6-paid enrolment → has_receipt=true → button → PDF opens. Reuses the portal shell + result
panel + F1 tokens.

## 2026-07-06 — FE#8a backend: admin roster read (staff-gated, tenant+BU-scoped cross-student) ✅

The staff side INVERTS the student /me/* model: not own-scoping, but tenant + BU correctness +
the staff-role/client-rejection/flag gate. Two read endpoints, reusing the existing academy
staff gate (require_feature + get_current_context + _require_staff) + `tenant_id==_tid(ctx)` +
`business_unit_id=='ACADEMY'` verbatim.
- **`GET /api/academy/enrollments`** — roster across students (filters status/course_id/cohort_id);
  each row = enrolment (status/score/discount/final_fee/payment_status/has_receipt) + course +
  cohort + UNMASKED student (name/email/college_student_id/college_name). has_receipt in one
  batched query. No pagination (matches list_courses; flag for large cohorts).
- **`GET /api/academy/enrollments/{id}`** — staff detail: full enrolment + unmasked student
  (+ course_degree/year_of_study/dob) + payment + test blocks. Id outside the staff's tenant/BU
  → 404 (no existence oracle across the tenant boundary).
- **phone_enc/pan_enc EXCLUDED** everywhere (envelope-encrypted PII; a separate access decision).
- The GATE is load-bearing (not own-scoping): flag-off→404, no session→401, STUDENT academy
  session→401 (student cookie ≠ staff), bound CLIENT session→403 (no cross-client leak), staff→
  200 sees ALL in-tenant (cross-student is CORRECT), tenant isolation (a real 2nd tenant's
  enrolment invisible + its id→404), filters, student /me stays own-scoped. Tests 326→334.
- NO migration (reads on existing tables; dev 0040). Dev-probed on real RDS.

## 2026-07-08 — FE#8a frontend: admin academy roster (staff table + detail) ✅ (local-verified)

The FIRST staff academy page — in the STAFF world ((admin) route group, staff access_token,
/admin/* middleware role=admin), NOT the (student) group/academy cookie. Frontend only,
local-verified (no deploy target, C1).
- **/admin/academy/enrollments** — cross-student roster onto GET /academy/enrollments: unmasked
  student (name/email/college), course, cohort, status, score, discount, fee, payment. Filters
  status/course/cohort (cohort populated from the selected course), wired to the query params.
  + an "Academy" admin nav entry. **/admin/academy/enrollments/{id}** — detail: full unmasked
  student (+ degree/year/DOB), aptitude-test block, pricing, payment. NO phone/PAN (the API
  excludes them; verified the whole detail payload).
- READ-ONLY — NO mutation controls (issue/status-move/waive = 8b, gated on the transition-machine
  STOP-0); the detail actions slot is intentionally EMPTY, not stubbed.
- Reused F1 admin components (AppShell/SectionCard/StatusPill/EmptyState/Skeleton + lib/api), NOT
  the student storefront styling. 401 → /login?role=admin (staff login, not academy).
- Staff-gate verified BOTH layers (reverse of the student gate): a STUDENT academy session →
  /admin/academy/* → 307 → staff login (middleware) AND the roster API → 401.

## 2026-07-08 — 8b-1: academy enrolment transition machine + refactor the two writers through it ✅

`app/academy_transitions.py::transition(db, enr, to_state, *, kind, reason, actor, ctx)` — the
SINGLE authority for enrolment.status. Tagged edge table (system|manual); machine-enforced,
fail-closed: not-in-table→409, a [system] edge from a manual caller→409 (so a manual move can
NEVER reach 'active' — offered→active is system-only), a move FROM a terminal state
(cancelled/dropped/completed)→409 via an explicit TERMINAL set check, manual moves REQUIRE a
reason (422). `applied→tested` deliberately absent (dead vocabulary — no writer). Every successful
move emits an `academy.enrollment.transition` audit {from,to,kind,reason,actor} via the existing
write_audit/shared.audit_logs — the status-transition trail that did NOT exist before (finding #6).
- Refactored the ONLY two production writers through it, behaviour UNCHANGED: grade (take.py,
  applied|tested→offered, actor=aptitude_engine) + pay (_activate_payment, offered→active,
  actor=payment). payment_status='paid' stays a SEPARATE axis (not routed). The pay path now
  writes BOTH the pre-existing payment audit AND the new transition audit (added, not replaced).
- NO new mutation surface (manual-move=8b-2, fee-waive=8b-3). NO migration (existing audit
  mechanism; dev stays head 0040). Tests 334→342 (rejections + reason + both writers routed +
  now-audited). Dev-probed on real RDS (audit rows appear where they didn't before).
- PENDING flagged: NO production enrolment-CREATE path (the whole student track walks seed-created
  enrolments).

## 2026-07-08 — 8b-2: STAFF manual status-move endpoint (a manual caller of the 8b-1 machine) ✅

`POST /api/academy/enrollments/{id}/status` {to_state, reason} — staff-gated, tenant/BU-scoped
(reuses the 8a gate verbatim: require_feature + get_current_context + _require_staff +
tenant_id==_tid(ctx) + BU=='ACADEMY'; an id outside → 404, no oracle). DELEGATES legality to
academy_transitions.transition(kind="manual") — the single authority; the endpoint does NOT
duplicate the machine's rules. Its own two checks: to_state must be a known status value (422)
and tenant/BU ownership (404). Everything the machine rejects surfaces through it: a manual
→active (system edge) → 409 (so a manual move STRUCTURALLY cannot activate a non-payer, proven
by the endpoint not pre-empting it), from-terminal → 409, not-in-table → 409, missing reason →
422. actor = the staff user (ctx.user_id) → the transition audit is attributable to a PERSON,
not a system actor. No-op (same-state) naturally 409s via the machine — no special-casing.
NO new mutation beyond this endpoint (fee-waive = 8b-3). NO migration (existing tables + audit
mechanism; dev 0040). Tests 342→347 (gate + tenant isolation + happy moves w/ staff actor +
delegation of all rejections). Dev-probed on real RDS.

## 2026-07-08 — 8b-3: fee-waive (generalize the activation seam; waive endpoint; dashboard branch) ✅

'active' keeps EXACTLY ONE entry point (the activation seam) — a waiver is activation WITHOUT
money, routed through the same offered→active [system] transition, NOT a manual status-move.
- Seam split: `_activate_core(...)` = the transition (via the 8b-1 machine) + the confirmation
  email (parameterized template + idempotency key) — the ONE entry to 'active', shared by both
  paths. `_activate_payment` (PAYMENT, behaviour UNCHANGED): pay→paid + payment_status='paid'
  +payment_id + receipt PDF→S3 + payment_activate audit, THEN core(academy_enrolment_active,
  key=academy:payment_confirmed:{pay.id}). `_activate_waiver` (WAIVER, new): NO Payment row, NO
  receipt, payment_status='waived' (NO payment_id), THEN core(academy_enrolment_waived,
  key=academy:fee_waived:{enr.id}).
- `POST /academy/enrollments/{id}/waive` {reason} — staff-gated + tenant/BU-scoped (reuses the
  8a/8b-2 gate; id outside → 404). reason REQUIRED (422). Precondition status=='offered' (else
  409; double-waive 409s — mirrors the pay precondition). actor = the staff user → attributable.
  Emits a distinct academy.enrolment.fee_waived audit {reason, actor} ON TOP of the core's
  transition audit.
- A waiver creates NO Payment row and NO receipt: has_receipt stays correctly FALSE, and the
  FE#7 receipt endpoint 404s (coherent, not a gap). New waiver email template
  academy_enrolment_waived — must NOT say "payment received".
- Frontend: dashboard 'waived' branch ("✓ Enrolled — fee waived", no receipt button) — three-way
  paid|waived|pending; fixes the latent bug where a waived enrolment showed "Proceed to payment".
- MIGRATION 0041 (data-only — 'waived' is an existing CHECK value): seeds the waiver template via
  the idempotent seed_notification_templates (mirrors 0037/0039/0040). Dev 0040→0041.
- Tests 347→352 (waiver no-Payment-row + has_receipt-false coherence + payment-path-unchanged +
  gate + tenant isolation + preconditions). Dev-probed on real RDS.

## 2026-07-08 — 8b frontend controls: admin status-move + waive buttons (the 8a actions slot) ✅ (local)

The staff mutation surface's UI. The 8a detail view's empty actions slot now renders STATE-AWARE
controls onto the dev-proven 8b-2 (POST .../status) + 8b-3 (POST .../waive) endpoints. Frontend
only, local-verified (no deploy target, C1).
- actionsFor(status) is the frontend MIRROR of the 8b-1 transition table — renders ONLY the moves
  legal FROM the current status: offered→[Waive fee][Cancel], applied/tested→[Cancel],
  active→[Mark completed][Mark dropped], terminal→none. NEVER an "activate" control (grep-proven:
  the only to_state values are cancelled/completed/dropped) — 'active' is reached only by pay/waive.
- Truthfulness proven functionally: the controls the UI hides genuinely 409 on the backend
  (offered→completed/active 409; active→cancelled 409; terminal→any 409), the shown ones 200.
- ActionModal (mirrors the F1 assessments WaiveModal): REQUIRED reason (submit disabled until
  non-empty — mirrors the backend 422), in-flight guard (synchronous useRef + disabled button →
  ONE request per confirm, the FE#6 discipline). On success → setD(null)+re-read (controls
  recompute from the fresh status; no stale-control window). On the machine's 409 race → show +
  re-read. Reuses F1 admin chrome (SectionCard/StatusPill/AppShell), not the storefront.
- This completes the staff academy mutation surface: 8b-1 machine + 8b-2 status-move + 8b-3
  fee-waive, now with staff UI.

## 2026-07-09 — CREATE-1: enrolment CREATE (apply endpoint + public applyable-cohorts read) ✅

The FIRST production creator of an 'applied' enrolment — the machine's entry state, seed-only
until now. Closes the load-bearing PENDING gap (the whole student track had walked SEED-created
enrolments).
- POST /academy/students/me/enrollments {course_id, cohort_id} — get_current_student-gated,
  OWN-SCOPED (student_id from the SESSION, never the body). Validates in order: published course
  (404) → cohort belongs to it + applyable (422) → course-level dedup, no LIVE enrolment (409
  ALREADY_APPLIED) → plain INSERT at status='applied' (payment_status='pending', all else NULL),
  NO transition() (creation is upstream of the machine — no ∅→applied edge). Catches
  UNIQUE(cohort_id,student_id) as 409 (double-submit-safe, never a 500). Emits an
  academy.enrolment.apply audit.
- GET /academy/public/courses/{slug}/cohorts — PUBLIC storefront read; published-only gate;
  returns APPLYABLE cohorts ({planned, open}; running/completed/cancelled excluded); empty list
  when none open. tenant-by-Host.
- SETTLED: apply-after-login + student-picks-cohort + one-live-per-course. Applyable = planned+open
  (defined here; no prior predicate). Live = status NOT IN (dropped, cancelled) → terminal re-appliable.
- NO migration (reads + insert on existing tables; the course-level dedup is ENDPOINT-enforced,
  NOT a new constraint; the pre-existing UNIQUE(cohort,student) is caught). Dev stays 0041.
- Tests 352→359 (own-scoping + course-dedup w/ terminal re-apply + same-cohort double-submit +
  validation + gate + public read). Dev-probed: the FULL chain (apply→issue→take→grade→offered→
  pay→active+receipt) runs on the student-CREATED enrolment, indistinguishable from a seed row.

## 2026-07-09 — create-2 backend: course_id envelope on the public cohorts read ✅

Read-shape for create-2 (storefront apply wiring) surfaced the one gap the two dev-proven
endpoints couldn't cover: apply needs course_id, but no public/student read exposed it (the
course-detail read's allowlist hides id; the cohorts read carried cohort_id only). Option A —
the minimal read-addition (same pattern as FE#5 course.fee / FE#7 has_receipt).
- GET /public/courses/{slug}/cohorts now returns `{ course_id, cohorts: [...] }` (was a bare
  list). The endpoint already resolves the course by slug + returns cohort_id; carrying the
  resolved course_id is consistent, not a new exposure class (UUID, not PII; apply re-validates
  published + cohort-belongs-to-course under get_current_student). The course-DETAIL read keeps
  its no-id allowlist. Object shape → the empty-cohorts case still carries the id, so the
  frontend can render "no open cohorts" AND still have the id.
- The two endpoints now compose: the course_id the storefront read hands out is the id apply
  accepts. NO migration (response-shape change on an existing read; dev 0041). Tests still 359
  (test_academy_apply updated for the envelope). Dev-probed: envelope + round-trip into apply.

## Pending / next steps

➡️ **The canonical, durable register of ALL outstanding/deferred items is
[`docs/PENDING.md`](PENDING.md)** — read it each session before assuming anything is
done. (This list is no longer maintained here to avoid two diverging copies.)

Infra already applied: security groups, RDS, Redis, ECS Fargate (backend live), ALB +
HTTPS/ACM (dev-api serves HTTPS).
