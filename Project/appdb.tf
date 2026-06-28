# ── SPS Shared · dev · least-privilege application DB role (append-only audit) ──
# The backend connects as `sps_app` (NOT the RDS master), which has full DML on
# business tables but only SELECT/INSERT on shared.audit_logs + shared.consents —
# so append-only is DB-ENFORCED for the app (owners bypass GRANT/REVOKE, hence a
# non-owner role). The MIGRATE task keeps the master credential (it runs DDL);
# tests/maintenance use master too, so cleanup still works.
#
# The role itself (CREATE ROLE + GRANTs) is provisioned out-of-band by a one-off
# bootstrap ECS task (RDS is private; the password comes from this secret and is
# never in git/Terraform state as plaintext beyond the secret).

resource "random_password" "app_db" {
  length  = 32
  special = false # alphanumeric → safe to interpolate into CREATE/ALTER ROLE
}

resource "aws_secretsmanager_secret" "app_db" {
  name        = "${local.name_prefix}-app-db"
  description = "Least-privilege application DB role (sps_app) credentials"

  tags = {
    Name     = "${local.name_prefix}-app-db"
    Vertical = "shared"
  }
}

resource "aws_secretsmanager_secret_version" "app_db" {
  secret_id     = aws_secretsmanager_secret.app_db.id
  secret_string = jsonencode({ username = "sps_app", password = random_password.app_db.result })
}

data "aws_iam_policy_document" "read_app_db_secret" {
  statement {
    sid       = "ReadAppDbSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app_db.arn]
  }
}

# Execution role: inject DB_USER/DB_PASSWORD into the BACKEND task def at start.
resource "aws_iam_role_policy" "execution_app_db_secret" {
  name   = "${local.name_prefix}-exec-app-db-secret"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.read_app_db_secret.json
}

# Task role: lets the one-off bootstrap task read the sps_app password via boto3.
resource "aws_iam_role_policy" "task_app_db_secret" {
  name   = "${local.name_prefix}-task-app-db-secret"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.read_app_db_secret.json
}
