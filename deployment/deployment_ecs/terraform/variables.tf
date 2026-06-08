###############################################################################
# Root variables
###############################################################################

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "aws_account_id" {
  description = "AWS account ID (used in IAM ARNs)"
  type        = string
}

variable "environment" {
  description = "Deployment environment (prod | staging)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "environment must be 'prod' or 'staging'."
  }
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for HTTPS on the ALB (must be in same region)"
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "CIDRs allowed to reach the ALB (default: open)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "mwaa_environment_class" {
  description = "MWAA environment class (mw1.small | mw1.medium | mw1.large)"
  type        = string
  default     = "mw1.small"
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications (leave empty to skip)"
  type        = string
  default     = ""
}

  description = "Maximum MWAA workers"
  type        = number
  default     = 5
}
