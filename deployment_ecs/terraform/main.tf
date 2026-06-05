###############################################################################
# Data Governance Copilot — Root Terraform
# Modules: VPC, ECR, RDS (pgvector), ElastiCache, ALB, ECS, MWAA, IAM, Secrets
###############################################################################

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state — S3 backend (bucket + DynamoDB table created separately via bootstrap)
  backend "s3" {
    bucket         = "dgc-terraform-state"       # change to your bucket
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"                # Mumbai (closest to Uttarakhand)
    encrypt        = true
    dynamodb_table = "dgc-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "data-governance-copilot"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

###############################################################################
# Locals — derived values used across modules
###############################################################################
locals {
  name_prefix = "dgc-${var.environment}"

  # Services deployed on ECS
  ecs_services = {
    api = {
      image_name     = "dgc-api"
      container_port = 8000
      cpu            = 1024
      memory         = 2048
      desired_count  = 2
      health_path    = "/health"
    }
    app = {
      image_name     = "dgc-app"
      container_port = 8501
      cpu            = 512
      memory         = 1024
      desired_count  = 1
      health_path    = "/_stcore/health"
    }
    mcp_server = {
      image_name     = "dgc-mcp"
      container_port = 8002
      cpu            = 512
      memory         = 1024
      desired_count  = 1
      health_path    = "/health"
    }
  }
}

###############################################################################
# Modules
###############################################################################

module "vpc" {
  source      = "./modules/vpc"
  name_prefix = local.name_prefix
  aws_region  = var.aws_region
}

module "ecr" {
  source      = "./modules/ecr"
  name_prefix = local.name_prefix
  services    = keys(local.ecs_services)
}

module "iam" {
  source      = "./modules/iam"
  name_prefix = local.name_prefix
  aws_region  = var.aws_region
  aws_account = var.aws_account_id
}

module "secrets" {
  source      = "./modules/secrets"
  name_prefix = local.name_prefix
}

module "rds" {
  source                = "./modules/rds"
  name_prefix           = local.name_prefix
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  app_security_group_id = module.ecs.app_security_group_id
  db_password_secret_arn = module.secrets.db_password_secret_arn
}

module "elasticache" {
  source             = "./modules/elasticache"
  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  app_security_group_id = module.ecs.app_security_group_id
}

module "alb" {
  source            = "./modules/alb"
  name_prefix       = local.name_prefix
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  certificate_arn   = var.acm_certificate_arn
  ecs_services      = local.ecs_services
}

module "ecs" {
  source                  = "./modules/ecs"
  name_prefix             = local.name_prefix
  aws_region              = var.aws_region
  aws_account_id          = var.aws_account_id
  vpc_id                  = module.vpc.vpc_id
  private_subnet_ids      = module.vpc.private_subnet_ids
  alb_security_group_id   = module.alb.alb_security_group_id
  target_group_arns       = module.alb.target_group_arns
  ecs_task_role_arn       = module.iam.ecs_task_role_arn
  ecs_execution_role_arn  = module.iam.ecs_execution_role_arn
  ecr_repository_urls     = module.ecr.repository_urls
  secrets_arns            = module.secrets.all_secret_arns
  ecs_services            = local.ecs_services

  # Runtime config injected as env vars
  rds_endpoint            = module.rds.endpoint
  rds_secret_arn          = module.secrets.db_password_secret_arn
  redis_endpoint          = module.elasticache.primary_endpoint
  rds_db_name             = module.rds.db_name
}

module "monitoring" {
  source           = "./modules/monitoring"
  name_prefix      = local.name_prefix
  aws_region       = var.aws_region
  aws_account_id   = var.aws_account_id
  ecs_cluster_name = module.ecs.cluster_name
  ecs_services     = local.ecs_services
  rds_identifier   = "${local.name_prefix}-postgres"
  redis_group_id   = "${local.name_prefix}-redis"
  alb_arn_suffix   = module.alb.alb_arn_suffix
  alert_email      = var.alert_email
}

module "mwaa" {
  source             = "./modules/mwaa"
  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  mwaa_role_arn      = module.iam.mwaa_role_arn
  dags_s3_bucket     = module.mwaa.dags_bucket_id
  environment_name   = "${local.name_prefix}-airflow"
  rds_endpoint       = module.rds.endpoint
  secrets_arns       = module.secrets.all_secret_arns
}
