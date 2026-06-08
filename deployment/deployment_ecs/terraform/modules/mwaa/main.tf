###############################################################################
# Module: MWAA (Amazon Managed Workflows for Apache Airflow)
# Replaces self-managed Airflow on ECS (P1 hardening item)
# - Existing DAGs are compatible without modification
# - S3 bucket for DAGs + requirements.txt + plugins
# - Logs → CloudWatch
# - Private network mode (access via VPN or bastion)
###############################################################################

variable "name_prefix"         { type = string }
variable "vpc_id"              { type = string }
variable "private_subnet_ids"  { type = list(string) }
variable "mwaa_role_arn"       { type = string }
variable "dags_s3_bucket"      { type = string }
variable "environment_name"    { type = string }
variable "rds_endpoint"        { type = string }
variable "secrets_arns"        { type = map(string) }

variable "environment_class"   { type = string; default = "mw1.small" }
variable "max_workers"         { type = number; default = 5 }
variable "min_workers"         { type = number; default = 1 }
variable "schedulers"          { type = number; default = 2 }

###############################################################################
# S3 Bucket for DAGs
###############################################################################
resource "aws_s3_bucket" "dags" {
  bucket        = "${var.name_prefix}-mwaa-dags"
  force_destroy = false
  tags          = { Name = "${var.name_prefix}-mwaa-dags" }
}

resource "aws_s3_bucket_versioning" "dags" {
  bucket = aws_s3_bucket.dags.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dags" {
  bucket = aws_s3_bucket.dags.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dags" {
  bucket                  = aws_s3_bucket.dags.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# Upload a minimal requirements.txt so MWAA knows what to install
# (Your full requirements.txt should be uploaded via CI/CD)
###############################################################################
resource "aws_s3_object" "requirements" {
  bucket  = aws_s3_bucket.dags.id
  key     = "requirements.txt"
  content = <<-EOF
    apache-airflow-providers-amazon>=8.0.0
    apache-airflow-providers-postgres>=5.0.0
    apache-airflow-providers-http>=4.0.0
    langchain>=0.2.0
    langchain-community>=0.2.0
    openai>=1.0.0
    psycopg2-binary>=2.9.0
    boto3>=1.34.0
  EOF

  etag = md5(<<-EOF
    apache-airflow-providers-amazon>=8.0.0
    apache-airflow-providers-postgres>=5.0.0
    apache-airflow-providers-http>=4.0.0
    langchain>=0.2.0
    langchain-community>=0.2.0
    openai>=1.0.0
    psycopg2-binary>=2.9.0
    boto3>=1.34.0
  EOF
  )
}

###############################################################################
# Security Group for MWAA
###############################################################################
resource "aws_security_group" "mwaa" {
  name        = "${var.name_prefix}-mwaa-sg"
  description = "MWAA environment — allow self + egress"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
    description = "MWAA internal communication"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-mwaa-sg" }
}

###############################################################################
# MWAA Environment
###############################################################################
resource "aws_mwaa_environment" "main" {
  name              = var.environment_name
  airflow_version   = "2.9.2"
  environment_class = var.environment_class
  max_workers       = var.max_workers
  min_workers       = var.min_workers
  schedulers        = var.schedulers

  execution_role_arn = var.mwaa_role_arn

  source_bucket_arn    = aws_s3_bucket.dags.arn
  dag_s3_path          = "dags/"
  requirements_s3_path = "requirements.txt"

  network_configuration {
    security_group_ids = [aws_security_group.mwaa.id]
    subnet_ids         = slice(var.private_subnet_ids, 0, 2)  # MWAA needs exactly 2 subnets
  }

  webserver_access_mode = "PRIVATE_ONLY"  # access via VPN/bastion

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }
    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }
    task_logs {
      enabled   = true
      log_level = "INFO"
    }
    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }
    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  # Airflow config overrides — align with project settings
  airflow_configuration_options = {
    "core.load_examples"                = "false"
    "core.default_timezone"             = "UTC"
    "webserver.dag_default_view"        = "grid"
    "scheduler.dag_dir_list_interval"   = "30"
    "celery.worker_concurrency"         = "16"
    # Point to RDS for Airflow metadata DB
    "database.sql_alchemy_conn"         = "postgresql+psycopg2://dgcadmin:{{resolve:secretsmanager:${var.secrets_arns["db_password"]}}}@${split(":", var.rds_endpoint)[0]}:5432/airflow"
    "database.sql_alchemy_pool_size"    = "5"
    "database.sql_alchemy_max_overflow" = "10"
  }

  tags = { Name = "${var.name_prefix}-mwaa" }

  lifecycle {
    ignore_changes = [
      # Plugin/requirements S3 paths updated by CI/CD, not Terraform
      plugins_s3_object_version,
      requirements_s3_object_version
    ]
  }
}

###############################################################################
# Outputs
###############################################################################
output "webserver_url"  { value = "https://${aws_mwaa_environment.main.webserver_url}" }
output "dags_bucket_id" { value = aws_s3_bucket.dags.id }
output "dags_bucket_arn" { value = aws_s3_bucket.dags.arn }
