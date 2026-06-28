# ── SPS Shared · dev · hCaptcha bot-gate secret (INERT scaffold) ────────────────
# hCaptcha protects public candidate registration. The app already supports both
# modes (app/captcha.py): real `siteverify` when HCAPTCHA_SECRET is non-empty,
# else LOCAL test mode (a present token passes). This file wires the secret
# CONTAINER + IAM + task-def env so real keys can be dropped in later — but ships
# INERT: the seeded value is EMPTY, so the app stays in test mode until a real key
# is set OUT-OF-BAND. No real key ever lives in git/Terraform.
#
# To go live (STOP-4, needs an hCaptcha account):
#   aws secretsmanager put-secret-value --secret-id sps-shared-dev-hcaptcha \
#     --secret-string '{"secret":"<REAL_HCAPTCHA_SECRET>"}' --profile sps --region ap-south-1
#   (and set var.hcaptcha_sitekey to the public site key), then redeploy.

resource "aws_secretsmanager_secret" "hcaptcha" {
  name        = "${local.name_prefix}-hcaptcha"
  description = "hCaptcha server-side secret (siteverify). Real value set OUT-OF-BAND; never in git/TF."

  tags = {
    Name     = "${local.name_prefix}-hcaptcha"
    Vertical = "shared"
  }
}

# Seed an EMPTY placeholder so ECS can resolve HCAPTCHA_SECRET at container start
# (empty → app stays in test mode). `ignore_changes` ensures Terraform NEVER
# clobbers the real value once it's set out-of-band.
resource "aws_secretsmanager_secret_version" "hcaptcha" {
  secret_id     = aws_secretsmanager_secret.hcaptcha.id
  secret_string = jsonencode({ secret = "" })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_iam_policy_document" "read_hcaptcha_secret" {
  statement {
    sid       = "ReadHcaptchaSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.hcaptcha.arn]
  }
}

# Execution role: inject HCAPTCHA_SECRET into the backend task def at start.
resource "aws_iam_role_policy" "execution_hcaptcha_secret" {
  name   = "${local.name_prefix}-exec-hcaptcha-secret"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.read_hcaptcha_secret.json
}
