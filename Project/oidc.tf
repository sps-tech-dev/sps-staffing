# ── SPS Shared · GitHub Actions → AWS OIDC (dev deploy) ─────────
# Lets GitHub Actions assume a least-privilege deploy role via OIDC (no long-
# lived AWS keys). Trust is scoped to ONLY the develop branch of ONLY this repo.
# Branching model: develop → dev env (this role); main → prod later (no role yet).

# Task-definition family ARNs (revision-agnostic — new revisions get new ARNs,
# so scope to the family with a :* revision wildcard).
locals {
  td_backend_arn = "arn:aws:ecs:${var.aws_region}:${var.account_id}:task-definition/${local.name_prefix}-backend:*"
  td_migrate_arn = "arn:aws:ecs:${var.aws_region}:${var.account_id}:task-definition/${local.name_prefix}-migrate:*"
  cluster_tasks  = "arn:aws:ecs:${var.aws_region}:${var.account_id}:task/${local.name_prefix}-cluster/*"
  gha_sub        = "repo:sps-tech-dev/sps-staffing:ref:refs/heads/develop"
}

# ── OIDC provider for GitHub Actions ─────────────────────────────
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's well-known OIDC thumbprints. NOTE: since 2023 AWS validates this IdP
  # against its own trust store and does not rely on the thumbprint, but the
  # argument is still accepted; both documented values are included.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  tags = {
    Name     = "${local.name_prefix}-github-oidc"
    Vertical = "shared"
  }
}

# ── Trust policy: only develop branch of sps-tech-dev/sps-staffing ──
data "aws_iam_policy_document" "gha_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.gha_sub] # repo:sps-tech-dev/sps-staffing:ref:refs/heads/develop
    }
  }
}

resource "aws_iam_role" "gha_deploy" {
  name               = "${local.name_prefix}-gha-deploy"
  assume_role_policy = data.aws_iam_policy_document.gha_trust.json

  tags = {
    Name     = "${local.name_prefix}-gha-deploy"
    Vertical = "shared"
  }
}

# ── Least-privilege deploy permissions (build → push → deploy) ───
data "aws_iam_policy_document" "gha_deploy" {
  # ECR auth token — REQUIRES "*" (not resource-scopable by AWS).
  statement {
    sid       = "EcrAuthToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # ECR push/pull — scoped to the backend repo ONLY.
  statement {
    sid = "EcrPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.backend.arn]
  }

  # ECS task-def registration + describe — REQUIRE "*" (RegisterTaskDefinition
  # and DescribeTaskDefinition do not support resource-level permissions).
  statement {
    sid       = "EcsTaskDefRegister"
    actions   = ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"]
    resources = ["*"]
  }

  # ECS service update/describe — scoped to the backend service.
  statement {
    sid       = "EcsServiceDeploy"
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = [aws_ecs_service.backend.id]
  }

  # ECS run-task (migrate) + describe tasks — scoped to migrate task-def family
  # and this cluster's tasks.
  statement {
    sid       = "EcsRunMigrate"
    actions   = ["ecs:RunTask"]
    resources = [local.td_migrate_arn]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }
  statement {
    sid       = "EcsDescribeTasks"
    actions   = ["ecs:DescribeTasks"]
    resources = [local.cluster_tasks]
  }

  # PassRole — ONLY the ECS execution + task roles, ONLY to ecs-tasks.
  statement {
    sid       = "PassEcsRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_execution.arn, aws_iam_role.ecs_task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # CloudWatch Logs — read/tail the deploy + migrate log groups.
  statement {
    sid = "LogsRead"
    actions = [
      "logs:GetLogEvents",
      "logs:FilterLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = [
      "${aws_cloudwatch_log_group.backend.arn}:*",
      "${aws_cloudwatch_log_group.migrate.arn}:*",
    ]
  }
  # DescribeLogGroups requires "*" (not resource-scopable).
  statement {
    sid       = "LogsDescribe"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "gha_deploy" {
  name   = "${local.name_prefix}-gha-deploy"
  role   = aws_iam_role.gha_deploy.id
  policy = data.aws_iam_policy_document.gha_deploy.json
}
