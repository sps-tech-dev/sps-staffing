# ── SPS Shared · dev ACM certificate for dev-api.spstechnosoft.com ─
# DNS hosted at GoDaddy (NOT Route 53), so the DNS validation CNAME must be
# added MANUALLY at GoDaddy — Terraform cannot create the validation record.
# The exact CNAME (name/type/value) is exposed via the outputs below; it is
# only known AFTER the certificate resource is created (ACM assigns it).

resource "aws_acm_certificate" "main" {
  domain_name       = "dev-api.spstechnosoft.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name     = "${local.name_prefix}-api-cert"
    Vertical = "shared"
  }
}

# Waits for the certificate to reach ISSUED. With DNS hosted externally
# (GoDaddy) and no validation_record_fqdns provided, this BLOCKS until the
# GoDaddy CNAME below is added and ACM validates it (can take minutes once
# the record propagates). Stage 2 apply will sit here until that happens.
resource "aws_acm_certificate_validation" "main" {
  certificate_arn = aws_acm_certificate.main.arn
}
