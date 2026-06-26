# ── SPS Shared · dev S3 storage (file uploads) ──────────────────
# Shared bucket for resumes / candidate documents across all verticals.
# Stores personal data → DPDP: private only (no public access), encrypted,
# versioned, ap-south-1 (India residency). Access is exclusively via the app's
# IAM task role + pre-signed URLs. Key convention (see DECISIONS):
#   tenant=<id>/business_unit=<vertical>/<entity>/<file>

resource "aws_s3_bucket" "storage" {
  bucket = "${local.name_prefix}-storage-${var.account_id}" # sps-shared-dev-storage-412058343855

  tags = {
    Name     = "${local.name_prefix}-storage"
    Vertical = "shared"
  }
}

# Block ALL public access (mandatory — personal data under DPDP).
resource "aws_s3_bucket_public_access_block" "storage" {
  bucket                  = aws_s3_bucket.storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encryption at rest. AES256 (SSE-S3) for dev; SSE-KMS with a CMK is the prod
# upgrade (per-key access control + audit).
resource "aws_s3_bucket_server_side_encryption_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning — recover accidentally overwritten/deleted resumes & documents.
resource "aws_s3_bucket_versioning" "storage" {
  bucket = aws_s3_bucket.storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle: clean up abandoned multipart uploads. (Storage-class transitions
# e.g. → STANDARD_IA at 90d / expiry per DPDP retention can be added here later.)
resource "aws_s3_bucket_lifecycle_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ── Task-role access (least privilege — THIS bucket only) ────────
data "aws_iam_policy_document" "s3_storage_access" {
  statement {
    sid       = "ObjectRW"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.storage.arn}/*"]
  }
  statement {
    sid       = "ListThisBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.storage.arn]
  }
}

resource "aws_iam_role_policy" "task_s3_storage" {
  name   = "${local.name_prefix}-task-s3-storage"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.s3_storage_access.json
}
