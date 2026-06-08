###############################################################################
# Module: ElastiCache
# Redis 7 replication group (1 primary + 1 replica, 2 AZs)
# - TLS in-transit (tls_enabled)
# - At-rest encryption (KMS)
# - AUTH token stored in Secrets Manager
# - Automatic failover enabled
###############################################################################

variable "name_prefix"            { type = string }
variable "vpc_id"                 { type = string }
variable "private_subnet_ids"     { type = list(string) }
variable "app_security_group_id"  { type = string }

variable "node_type"     { type = string; default = "cache.t3.micro" }
variable "num_replicas"  { type = number; default = 1 }

###############################################################################
# Security Group — ECS tasks only
###############################################################################
resource "aws_security_group" "redis" {
  name        = "${var.name_prefix}-redis-sg"
  description = "Allow Redis from ECS app SG only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
    description     = "ECS app tasks"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-redis-sg" }
}

###############################################################################
# Subnet Group
###############################################################################
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name_prefix}-redis-subnet"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.name_prefix}-redis-subnet-group" }
}

###############################################################################
# KMS Key for at-rest encryption
###############################################################################
resource "aws_kms_key" "redis" {
  description             = "${var.name_prefix} ElastiCache encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = { Name = "${var.name_prefix}-redis-kms" }
}

resource "aws_kms_alias" "redis" {
  name          = "alias/${var.name_prefix}-redis"
  target_key_id = aws_kms_key.redis.key_id
}

###############################################################################
# AUTH Token (stored in Secrets Manager by the secrets module,
# referenced here via SSM-style random generation)
###############################################################################
resource "random_password" "redis_auth" {
  length  = 32
  special = false  # Redis AUTH doesn't allow special chars
}

resource "aws_secretsmanager_secret" "redis_auth" {
  name                    = "${var.name_prefix}/redis/auth-token"
  description             = "ElastiCache Redis AUTH token"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id     = aws_secretsmanager_secret.redis_auth.id
  secret_string = random_password.redis_auth.result
}

###############################################################################
# Parameter Group — Redis 7 with sensible defaults
###############################################################################
resource "aws_elasticache_parameter_group" "redis7" {
  name   = "${var.name_prefix}-redis7-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"  # LRU eviction — safe for cache workloads
  }

  parameter {
    name  = "activedefrag"
    value = "yes"
  }
}

###############################################################################
# Replication Group
###############################################################################
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name_prefix}-redis"
  description          = "DGC Redis cache + rate limiter"

  node_type            = var.node_type
  num_cache_clusters   = var.num_replicas + 1  # 1 primary + replicas
  parameter_group_name = aws_elasticache_parameter_group.redis7.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  engine_version       = "7.1"
  port                 = 6379

  at_rest_encryption_enabled  = true
  kms_key_id                  = aws_kms_key.redis.arn
  transit_encryption_enabled  = true
  auth_token                  = random_password.redis_auth.result
  auth_token_update_strategy  = "ROTATE"

  automatic_failover_enabled   = true
  multi_az_enabled             = true

  snapshot_retention_limit = 3
  snapshot_window          = "05:00-06:00"
  maintenance_window       = "sun:06:00-sun:07:00"

  apply_immediately = false

  tags = { Name = "${var.name_prefix}-redis" }
}

###############################################################################
# Outputs
###############################################################################
output "primary_endpoint" {
  description = "Redis primary endpoint (host:port) for app config"
  value       = "${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"
}

output "auth_secret_arn" {
  description = "Secrets Manager ARN for Redis AUTH token"
  value       = aws_secretsmanager_secret.redis_auth.arn
}

output "security_group_id" {
  value = aws_security_group.redis.id
}
