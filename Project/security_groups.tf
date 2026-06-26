# ── SPS Shared · dev security groups ────────────────────────────
# Layered least-privilege: internet → ALB → ECS → {RDS, Redis}.
# Rules are separate aws_security_group_rule resources so SG-to-SG
# references don't create dependency cycles.

# ── ALB ──────────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "ALB: public HTTP/HTTPS ingress"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name     = "${local.name_prefix}-alb-sg"
    Vertical = "shared"
  }
}

resource "aws_security_group_rule" "alb_ingress_http" {
  type              = "ingress"
  description       = "HTTP from anywhere"
  security_group_id = aws_security_group.alb.id
  protocol          = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb_ingress_https" {
  type              = "ingress"
  description       = "HTTPS from anywhere"
  security_group_id = aws_security_group.alb.id
  protocol          = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_security_group_rule" "alb_egress_all" {
  type              = "egress"
  description       = "All outbound"
  security_group_id = aws_security_group.alb.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

# ── ECS (Fargate) ────────────────────────────────────────────────
resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "ECS Fargate: app traffic from ALB only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name     = "${local.name_prefix}-ecs-sg"
    Vertical = "shared"
  }
}

resource "aws_security_group_rule" "ecs_ingress_from_alb" {
  type                     = "ingress"
  description              = "Container port from ALB"
  security_group_id        = aws_security_group.ecs.id
  protocol                 = "tcp"
  from_port                = var.container_port
  to_port                  = var.container_port
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "ecs_egress_all" {
  type              = "egress"
  description       = "All outbound"
  security_group_id = aws_security_group.ecs.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

# ── RDS (PostgreSQL) ─────────────────────────────────────────────
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "RDS PostgreSQL: 5432 from ECS only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name     = "${local.name_prefix}-rds-sg"
    Vertical = "shared"
  }
}

resource "aws_security_group_rule" "rds_ingress_from_ecs" {
  type                     = "ingress"
  description              = "PostgreSQL from ECS"
  security_group_id        = aws_security_group.rds.id
  protocol                 = "tcp"
  from_port                = 5432
  to_port                  = 5432
  source_security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "rds_egress_all" {
  type              = "egress"
  description       = "All outbound"
  security_group_id = aws_security_group.rds.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}

# ── Redis (ElastiCache) ──────────────────────────────────────────
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Redis: 6379 from ECS only"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name     = "${local.name_prefix}-redis-sg"
    Vertical = "shared"
  }
}

resource "aws_security_group_rule" "redis_ingress_from_ecs" {
  type                     = "ingress"
  description              = "Redis from ECS"
  security_group_id        = aws_security_group.redis.id
  protocol                 = "tcp"
  from_port                = 6379
  to_port                  = 6379
  source_security_group_id = aws_security_group.ecs.id
}

resource "aws_security_group_rule" "redis_egress_all" {
  type              = "egress"
  description       = "All outbound"
  security_group_id = aws_security_group.redis.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
}
