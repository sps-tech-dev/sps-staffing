# ── SPS Shared · dev RDS PostgreSQL data layer ──────────────────
# Single SHARED Postgres instance for all verticals: one database
# (sps_platform_dev) with schemas shared/staffing/academy/consulting
# created by Alembic (NOT Terraform). Single-AZ dev instance in the
# private-data subnets, reachable only from the ECS security group.
# Master credentials are generated here and stored in Secrets Manager
# — never output in plaintext.

# ── DB subnet group (both private-data subnets) ──────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-rds-subnet-group"
  subnet_ids = aws_subnet.private_data[*].id

  tags = {
    Name     = "${local.name_prefix}-rds-subnet-group"
    Vertical = "shared"
  }
}

# ── Master password (generated, stored in Secrets Manager) ───────
# Exclude / @ " and space so the password is safe in connection strings/URLs.
resource "random_password" "rds" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?.,"
}

# ── RDS instance ─────────────────────────────────────────────────
resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-rds"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  # Single-AZ for dev. Flip to true to upgrade to Multi-AZ for prod (HA failover).
  multi_az = false

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 100 # storage autoscaling cap (GB)
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  db_name  = var.db_name
  username = var.db_username
  password = random_password.rds.result

  backup_retention_period = 7
  # End state is protected (true). The rename forces a replacement of the
  # existing (empty) instance; AWS blocks deleting a protected instance, so
  # BEFORE apply disable protection on the OLD instance via CLI:
  #   aws rds modify-db-instance --db-instance-identifier sps-staffing-dev-rds \
  #     --no-deletion-protection --apply-immediately --profile sps --region ap-south-1
  # The new sps-shared-dev-rds is then created with protection on (this file).
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-rds-final"
  apply_immediately         = true # dev: apply changes now rather than next window

  tags = {
    Name     = "${local.name_prefix}-rds"
    Tier     = "private-data"
    Vertical = "shared"
  }
}

# ── Secrets Manager: master credentials + connection info ────────
resource "aws_secretsmanager_secret" "rds_credentials" {
  name        = "${local.name_prefix}-rds-credentials"
  description = "RDS PostgreSQL master credentials and connection info for ${local.name_prefix}"

  tags = {
    Name     = "${local.name_prefix}-rds-credentials"
    Vertical = "shared"
  }
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id = aws_secretsmanager_secret.rds_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.rds.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = var.db_name
  })
}
