# ── SPS Shared · dev ECS Fargate (backend compute) ──────────────
# ARM64 Fargate service for the FastAPI backend, behind the ALB.
# COST: 1 task @ 256/512 ARM64 ≈ $9/mo if run 24/7. Pause when idle
# with scripts/ecs-scale.sh 0 (scales desired_count to 0). The ALB
# (alb.tf) is separate and always-on.

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled" # minor CloudWatch cost; useful per-task metrics in dev
  }

  tags = {
    Name     = "${local.name_prefix}-cluster"
    Vertical = "shared"
  }
}

# ── IAM: task execution role (ECR pull + CloudWatch logs) ────────
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = {
    Name     = "${local.name_prefix}-ecs-execution-role"
    Vertical = "shared"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ── IAM: task role (app's own AWS permissions) ───────────────────
# Now granted read on the RDS secret only (least privilege). This is also
# where S3 permissions attach later.
resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = {
    Name     = "${local.name_prefix}-ecs-task-role"
    Vertical = "shared"
  }
}

# Least-privilege: GetSecretValue on the RDS credentials secret ARN ONLY.
data "aws_iam_policy_document" "read_rds_secret" {
  statement {
    sid       = "ReadRdsSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.rds_credentials.arn]
  }
}

# Task role: lets the app read the secret at runtime (boto3) if it ever needs to.
resource "aws_iam_role_policy" "task_read_rds_secret" {
  name   = "${local.name_prefix}-task-read-rds-secret"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.read_rds_secret.json
}

# Execution role: REQUIRED so ECS can resolve the task def `secrets` block
# (DB_USER/DB_PASSWORD) from Secrets Manager at container start.
resource "aws_iam_role_policy" "execution_read_rds_secret" {
  name   = "${local.name_prefix}-exec-read-rds-secret"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.read_rds_secret.json
}

# ── Logs ─────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}-backend"
  retention_in_days = 14

  tags = {
    Name     = "/ecs/${local.name_prefix}-backend"
    Vertical = "shared"
  }
}

# ── Task definition ──────────────────────────────────────────────
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  # REQUIRED: the pushed image is arm64 — Fargate must run ARM64.
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      # Non-secret config. The app still boots if the data tier is unreachable
      # (connections are lazy; /healthz never touches DB/Redis).
      environment = [
        { name = "APP_ENV", value = var.environment },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "DB_HOST", value = aws_db_instance.main.address },
        { name = "DB_PORT", value = "5432" },
        { name = "DB_NAME", value = var.db_name },
        { name = "REDIS_HOST", value = aws_elasticache_replication_group.main.primary_endpoint_address },
        { name = "REDIS_PORT", value = "6379" },
        { name = "S3_BUCKET", value = aws_s3_bucket.storage.bucket },
        # PII envelope encryption: non-secret CMK id (key material stays in KMS).
        { name = "PII_KMS_KEY_ID", value = aws_kms_key.pii.arn },
        # hCaptcha public site key (non-secret). Empty → frontend uses the test key.
        { name = "HCAPTCHA_SITEKEY", value = var.hcaptcha_sitekey },
        # C1-1 cross-domain auth (see docs/DECISIONS): a cookie from dev-api.spstechnosoft.com
        # must reach a frontend on app-dev.spstechnosoft.com. Domain=.spstechnosoft.com +
        # SameSite=None + Secure (HTTPS-only, which dev-api is). Local (docker-compose) leaves
        # these unset → the same-origin Lax/host-only/insecure shape (inert-when-unset).
        { name = "COOKIE_SECURE", value = "true" },
        { name = "COOKIE_DOMAIN", value = ".spstechnosoft.com" },
        { name = "COOKIE_SAMESITE", value = "none" },
        { name = "CORS_ALLOWED_ORIGINS", value = var.frontend_origin },
      ]
      # Secrets injected from Secrets Manager (never plaintext in the task def).
      # The BACKEND connects as the least-privilege `sps_app` role (app-db secret)
      # → append-only DB-enforced on audit_logs/consents. The MIGRATE task keeps
      # the master rds_credentials secret (it runs DDL) — see migrate.tf.
      secrets = [
        { name = "DB_USER", valueFrom = "${aws_secretsmanager_secret.app_db.arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.app_db.arn}:password::" },
        { name = "PII_INDEX_KEY", valueFrom = "${aws_secretsmanager_secret.pii_index_key.arn}:index_key::" },
        # hCaptcha secret — seeded EMPTY (app stays in test mode); real key set out-of-band.
        { name = "HCAPTCHA_SECRET", valueFrom = "${aws_secretsmanager_secret.hcaptcha.arn}:secret::" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])

  tags = {
    Name     = "${local.name_prefix}-backend"
    Vertical = "shared"
  }
}

# ── Service ──────────────────────────────────────────────────────
resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  launch_type     = "FARGATE"
  desired_count   = var.backend_desired_count

  network_configuration {
    subnets          = aws_subnet.private_app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false # tasks reach ECR/logs via the NAT gateway
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 60

  depends_on = [aws_lb_listener.http]

  tags = {
    Name     = "${local.name_prefix}-backend"
    Vertical = "shared"
  }
}
