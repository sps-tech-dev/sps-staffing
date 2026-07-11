variable "aws_region" {
  type        = string
  description = "AWS region for all resources"
}

variable "account_id" {
  type        = string
  description = "AWS account ID"
}

variable "project" {
  type        = string
  description = "Project name, used for tagging and naming"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev/staging/prod)"
}

variable "frontend_origin" {
  type        = string
  description = "C1-1: the allowed frontend origin for credentialed CORS (the staging frontend pointed at dev-api). Explicit — never wildcard."
  default     = "https://app-dev.spstechnosoft.com"
}

variable "container_port" {
  type        = number
  description = "Port the ECS Fargate container listens on (ALB → ECS)"
  default     = 8000
}

# ── RDS ──────────────────────────────────────────────────────────
variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.small"
}

variable "db_engine_version" {
  type        = string
  description = "PostgreSQL engine major version"
  default     = "16"
}

variable "db_allocated_storage" {
  type        = number
  description = "Initial RDS storage in GB (gp3)"
  default     = 20
}

variable "db_name" {
  type        = string
  description = "Initial database name (Postgres: no hyphens — use underscores). One shared DB across all verticals."
  default     = "sps_platform_dev"
}

variable "db_username" {
  type        = string
  description = "RDS master username"
  default     = "spsadmin"
}

# ── Redis (ElastiCache) ──────────────────────────────────────────
variable "redis_node_type" {
  type        = string
  description = "ElastiCache node type"
  default     = "cache.t4g.micro"
}

variable "redis_engine_version" {
  type        = string
  description = "Redis engine version"
  default     = "7.1"
}

# ── ECS / compute ────────────────────────────────────────────────
variable "backend_image_tag" {
  type        = string
  description = "ECR image tag to deploy for the backend (immutable timestamp tag for traceable rollouts)"
  default     = "dev-20260626-222817"
}

variable "backend_cpu" {
  type        = number
  description = "Fargate task CPU units (256 = 0.25 vCPU)"
  default     = 256
}

variable "backend_memory" {
  type        = number
  description = "Fargate task memory (MiB)"
  default     = 512
}

variable "backend_desired_count" {
  type        = number
  description = "Desired number of backend tasks (set 0 to pause Fargate cost)"
  default     = 1
}

variable "hcaptcha_sitekey" {
  type        = string
  description = "hCaptcha PUBLIC site key for registration (non-secret). Empty = frontend uses the hCaptcha test key (test mode)."
  default     = ""
}
