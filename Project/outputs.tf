# ── SPS Staffing · networking outputs ───────────────────────────

output "vpc_id" {
  description = "ID of the dev VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB + NAT)"
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "Private app-tier subnet IDs (ECS Fargate)"
  value       = aws_subnet.private_app[*].id
}

output "private_data_subnet_ids" {
  description = "Private data-tier subnet IDs (RDS + Redis)"
  value       = aws_subnet.private_data[*].id
}

# ── Security groups ──────────────────────────────────────────────

output "alb_security_group_id" {
  description = "ALB security group ID"
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "ECS Fargate security group ID"
  value       = aws_security_group.ecs.id
}

output "rds_security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "Redis security group ID"
  value       = aws_security_group.redis.id
}

# ── RDS ──────────────────────────────────────────────────────────

output "rds_endpoint" {
  description = "RDS instance endpoint (host:port)"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.main.port
}

output "rds_secret_arn" {
  description = "ARN of the Secrets Manager secret holding RDS credentials"
  value       = aws_secretsmanager_secret.rds_credentials.arn
  sensitive   = true
}

# ── Redis (ElastiCache) ──────────────────────────────────────────

output "redis_endpoint" {
  description = "Redis primary endpoint address"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
  sensitive   = true
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.main.port
}

# ── ECR ──────────────────────────────────────────────────────────

output "ecr_repository_url" {
  description = "ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

# ── Compute ──────────────────────────────────────────────────────

output "alb_dns_name" {
  description = "Public DNS name of the ALB (backend entrypoint)"
  value       = aws_lb.main.dns_name
}

# ── S3 storage ───────────────────────────────────────────────────

output "s3_bucket_name" {
  description = "Name of the shared S3 storage bucket"
  value       = aws_s3_bucket.storage.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the shared S3 storage bucket"
  value       = aws_s3_bucket.storage.arn
}

# ── CI/CD ────────────────────────────────────────────────────────

output "gha_deploy_role_arn" {
  description = "ARN of the GitHub Actions OIDC deploy role (dev, develop branch)"
  value       = aws_iam_role.gha_deploy.arn
}

# ── ACM DNS validation — ADD THIS CNAME AT GODADDY ───────────────
# (Values are known only after the certificate is created.)

output "acm_validation_record_name" {
  description = "GoDaddy CNAME — HOST/NAME to add for ACM validation"
  value       = tolist(aws_acm_certificate.main.domain_validation_options)[0].resource_record_name
}

output "acm_validation_record_type" {
  description = "GoDaddy CNAME — record TYPE for ACM validation (CNAME)"
  value       = tolist(aws_acm_certificate.main.domain_validation_options)[0].resource_record_type
}

output "acm_validation_record_value" {
  description = "GoDaddy CNAME — VALUE/POINTS-TO for ACM validation"
  value       = tolist(aws_acm_certificate.main.domain_validation_options)[0].resource_record_value
}
