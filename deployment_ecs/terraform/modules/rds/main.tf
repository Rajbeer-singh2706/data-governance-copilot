###############################################################################
# Module: RDS
# PostgreSQL 16 with pgvector extension support
# - Multi-AZ for HA
# - Encrypted storage (KMS)
# - Enhanced monitoring + Performance Insights
# - Automatic minor version upgrades
# - Snapshot before destroy
# - Separate subnet group (private subnets only)
#
# pgvector is available as a PostgreSQL extension on RDS 15+.
# Run after provisioning:
#   psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
#   psql "$DATABASE_URL" -f scripts/init_neon.sql
###############################################################################

variable "name_prefix"            { type = string }
variable "vpc_id"                 { type = string }
variable "private_subnet_ids"     { type = list(string) }
variable "app_security_group_id"  { type = string }
variable "db_password_secret_arn" { type = string }

variable "db_instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "db_name" {
  type    = string
  default = "dgc"
}

variable "db_username" {
  type    = string
  default = "dgcadmin"
}

variable "allocated_storage"     { type = number; default = 50 }
variable "max_allocated_storage" { type = number; default = 200 }
variable "multi_az"              { type = bool;   default = true }
variable "deletion_protection"   { type = bool;   default = true }

###############################################################################
# Security Group — only ECS tasks can reach 5432
###############################################################################
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Allow PostgreSQL from ECS app SG only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
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

  tags = { Name = "${var.name_prefix}-rds-sg" }
}

###############################################################################
# DB Subnet Group
###############################################################################
resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-rds-subnet-group"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.name_prefix}-rds-subnet-group" }
}

###############################################################################
# Parameter Group — enable pgvector + logical replication
###############################################################################
resource "aws_db_parameter_group" "pg16" {
  name        = "${var.name_prefix}-pg16-params"
  family      = "postgres16"
  description = "DGC PostgreSQL 16 — pgvector optimised"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # log queries > 1s
  }

  parameter {
    name  = "rds.logical_replication"
    value = "1"
    apply_method = "pending-reboot"
  }
}

###############################################################################
# KMS Key for RDS encryption
###############################################################################
data "aws_caller_identity" "current" {}

resource "aws_kms_key" "rds" {
  description             = "${var.name_prefix} RDS encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = { Name = "${var.name_prefix}-rds-kms" }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.name_prefix}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

###############################################################################
# Enhanced Monitoring Role
###############################################################################
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name_prefix}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

###############################################################################
# RDS Instance
###############################################################################
resource "aws_db_instance" "main" {
  identifier        = "${var.name_prefix}-postgres"
  engine            = "postgres"
  engine_version    = "16.3"
  instance_class    = var.db_instance_class
  db_name           = var.db_name
  username          = var.db_username

  # Password pulled from Secrets Manager at apply time via data source
  password          = data.aws_secretsmanager_secret_version.db_password.secret_string

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage  # auto-scaling storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.pg16.name

  backup_retention_period   = 14
  backup_window             = "03:00-04:00"   # UTC
  maintenance_window        = "Sun:04:00-Sun:05:00"
  auto_minor_version_upgrade = true
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-final-snapshot"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring.arn
  enabled_cloudwatch_logs_exports       = ["postgresql", "upgrade"]

  tags = { Name = "${var.name_prefix}-rds" }
}

# Fetch the password Secrets Manager generated (see secrets module)
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = var.db_password_secret_arn
}

###############################################################################
# Outputs
###############################################################################
output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "db_name" {
  value = aws_db_instance.main.db_name
}

output "db_username" {
  value = aws_db_instance.main.username
}

output "security_group_id" {
  value = aws_security_group.rds.id
}
