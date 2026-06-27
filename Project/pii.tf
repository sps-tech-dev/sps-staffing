# ── SPS Shared · dev · PII field-encryption keys (Part 10) ──────────────
# Two SEPARATE keys for app-layer candidate PII protection:
#   1. KMS CMK  — envelope encryption (AES-256-GCM DEK) for PAN / phone (Aadhaar
#      later). The ECS *task* role calls GenerateDataKey (write) + Decrypt (read).
#   2. Secrets Manager secret — the HMAC key for deterministic blind indexes
#      (dedup / exact-match). The *execution* role injects it as PII_INDEX_KEY at
#      container start; the *task* role can also read it via boto3.
# Kept apart on purpose: leaking one grants neither the other's capability.
# Backend + migrate share ecs_task / ecs_execution, so the backfill task is
# covered without extra roles.

resource "aws_kms_key" "pii" {
  description             = "App-layer PII field encryption (envelope DEK) for ${local.name_prefix}"
  deletion_window_in_days = 30
  enable_key_rotation     = true # annual rotation of the CMK backing key

  # Root-account admin only; actual usage is delegated via the IAM role policies
  # below (least privilege — GenerateDataKey + Decrypt on this key only).
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableRootAccountAdmin"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      }
    ]
  })

  tags = {
    Name     = "${local.name_prefix}-pii"
    Vertical = "shared"
  }
}

resource "aws_kms_alias" "pii" {
  name          = "alias/sps-pii-dev"
  target_key_id = aws_kms_key.pii.key_id
}

# HMAC blind-index key: 32 random bytes (base64), SEPARATE from the CMK.
resource "random_id" "pii_index_key" {
  byte_length = 32
}

resource "aws_secretsmanager_secret" "pii_index_key" {
  name        = "${local.name_prefix}-pii-index-key"
  description = "HMAC-SHA256 key for candidate PII blind indexes (deterministic dedup/lookup)"

  tags = {
    Name     = "${local.name_prefix}-pii-index-key"
    Vertical = "shared"
  }
}

resource "aws_secretsmanager_secret_version" "pii_index_key" {
  secret_id     = aws_secretsmanager_secret.pii_index_key.id
  secret_string = jsonencode({ index_key = random_id.pii_index_key.b64_std })
}

# ── IAM: task role may use the CMK (GenerateDataKey on write, Decrypt on read) ──
data "aws_iam_policy_document" "pii_kms_use" {
  statement {
    sid       = "PiiEnvelopeEncryption"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [aws_kms_key.pii.arn]
  }
}

resource "aws_iam_role_policy" "task_pii_kms" {
  name   = "${local.name_prefix}-task-pii-kms"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.pii_kms_use.json
}

# ── IAM: GetSecretValue on the index-key secret (task=boto3, exec=secrets block) ──
data "aws_iam_policy_document" "pii_index_secret" {
  statement {
    sid       = "ReadPiiIndexKey"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.pii_index_key.arn]
  }
}

resource "aws_iam_role_policy" "task_pii_index_secret" {
  name   = "${local.name_prefix}-task-pii-index-secret"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.pii_index_secret.json
}

resource "aws_iam_role_policy" "execution_pii_index_secret" {
  name   = "${local.name_prefix}-exec-pii-index-secret"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.pii_index_secret.json
}

output "pii_kms_key_arn" {
  description = "ARN of the PII field-encryption CMK"
  value       = aws_kms_key.pii.arn
}
