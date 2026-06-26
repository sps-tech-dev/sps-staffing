# ── SPS Shared · dev Application Load Balancer ──────────────────
# Internet-facing ALB in the public subnets → backend target group.
# COST: an ALB is always-on (~$16/mo + LCU). It is NOT paused by the
# ecs-scale helper; scaling ECS to 0 stops Fargate cost only.

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name     = "${local.name_prefix}-alb"
    Vertical = "shared"
  }
}

# Fargate uses awsvpc networking → target_type must be "ip".
resource "aws_lb_target_group" "backend" {
  name        = "${local.name_prefix}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/healthz"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  tags = {
    Name     = "${local.name_prefix}-backend-tg"
    Vertical = "shared"
  }
}

# HTTP:80 listener — now ONLY redirects to HTTPS:443 (301, host/path preserved).
# Gated on cert validation so 80 isn't flipped to redirect until 443 exists.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }

  depends_on = [aws_acm_certificate_validation.main]

  tags = {
    Name     = "${local.name_prefix}-alb-http"
    Vertical = "shared"
  }
}

# HTTPS:443 listener → backend target group, using the validated ACM cert.
# Uses the validation resource's certificate_arn so it cannot apply before
# the cert is ISSUED.
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  depends_on = [aws_acm_certificate_validation.main]

  tags = {
    Name     = "${local.name_prefix}-alb-https"
    Vertical = "shared"
  }
}
