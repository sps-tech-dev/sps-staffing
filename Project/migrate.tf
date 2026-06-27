# ── SPS Shared · dev DB migration task (run-once) ───────────────
# A SEPARATE Fargate task that runs `alembic upgrade head` and exits — NOT a
# service, NOT wired to app startup. Same image/roles as the backend. Launch it
# deliberately via scripts/run-migration.sh. Migrations never run on app boot.

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/ecs/${local.name_prefix}-migrate"
  retention_in_days = 14

  tags = {
    Name     = "/ecs/${local.name_prefix}-migrate"
    Vertical = "shared"
  }
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${local.name_prefix}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn # pulls image + secret
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
      essential = true
      # Override the image's uvicorn CMD: run migrations and exit.
      command = ["alembic", "upgrade", "head"]
      environment = [
        { name = "APP_ENV", value = var.environment },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "DB_HOST", value = aws_db_instance.main.address },
        { name = "DB_PORT", value = "5432" },
        { name = "DB_NAME", value = var.db_name },
        # PII keys so the 0007 backfill encrypts in the SAME mode the app uses.
        { name = "PII_KMS_KEY_ID", value = aws_kms_key.pii.arn },
      ]
      secrets = [
        { name = "DB_USER", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.rds_credentials.arn}:password::" },
        { name = "PII_INDEX_KEY", valueFrom = "${aws_secretsmanager_secret.pii_index_key.arn}:index_key::" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.migrate.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migrate"
        }
      }
    }
  ])

  tags = {
    Name     = "${local.name_prefix}-migrate"
    Vertical = "shared"
  }
}
