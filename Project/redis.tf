# ── SPS Shared · dev Redis (ElastiCache) cache/broker layer ─────
# Single-node Redis in the private-data subnets, reachable only from
# the ECS security group. Holds only cache / broker data (sessions,
# rate limits, queues) — safe to recreate, so destroying just this
# file's resources during long idle periods is a valid cost lever.
#
# COST NOTE: ElastiCache has NO stop/start (unlike RDS). The only dev
# cost levers are (a) node size — already the smallest, cache.t4g.micro
# (~$11/mo) — or (b) `terraform destroy` of this layer when idle and
# `apply` to recreate it (data loss is acceptable: cache only).

# ── Subnet group (both private-data subnets) ─────────────────────
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private_data[*].id

  tags = {
    Name     = "${local.name_prefix}-redis-subnet-group"
    Vertical = "shared"
  }
}

# ── Replication group (single node, no replicas) ─────────────────
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "Redis cache/broker for ${local.name_prefix} (sessions, rate limits, queues)"

  engine         = "redis"
  engine_version = var.redis_engine_version
  node_type      = var.redis_node_type
  port           = 6379

  # Single node, no replicas — dev cost-saver.
  # PROD resilience upgrade: raise num_cache_clusters to 2+ and set
  # automatic_failover_enabled = true (and multi_az_enabled = true).
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  # transit_encryption_enabled left false for dev: enabling in-transit TLS
  # forces clients onto rediss:// (and AUTH-token handling), complicating the
  # dev client connection. PROD should set this to true.
  transit_encryption_enabled = false

  auto_minor_version_upgrade = true
  maintenance_window         = "sun:05:00-sun:06:00"
  apply_immediately          = true # dev: apply changes now rather than next window

  tags = {
    Name     = "${local.name_prefix}-redis"
    Tier     = "private-data"
    Vertical = "shared"
  }
}
