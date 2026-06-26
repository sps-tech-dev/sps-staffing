# ── SPS Shared · dev ECR (container registry) ───────────────────
# Shared registry for backend service images. Scan-on-push for basic
# vuln detection; lifecycle policy caps stored images to control cost.

resource "aws_ecr_repository" "backend" {
  name                 = "${local.name_prefix}-backend"
  image_tag_mutability = "MUTABLE" # dev: allow re-pushing :dev. Use IMMUTABLE for prod.

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name     = "${local.name_prefix}-backend"
    Vertical = "shared"
  }
}

# Keep only the last ~10 images to bound storage cost.
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
