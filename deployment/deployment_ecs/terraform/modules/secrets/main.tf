###############################################################################
# Module: Secrets Manager
# Creates secret placeholders for all app credentials.
# Terraform creates the secret; values are populated via:
#   aws secretsmanager put-secret-value --secret-id ... --secret-string ...
# OR the CI/CD pipeline injects them from GitHub Secrets on first deploy.
#
# Secrets created:
#   dgc-prod/db/password          ← RDS password (auto-generated)
#   dgc-prod/llm/groq-api-key
#   dgc-prod/llm/anthropic-api-key
#   dgc-prod/llm/openai-api-key
#   dgc-prod/llm/gemini-api-key
#   dgc-prod/integrations/jira
#   dgc-prod/integrations/collibra
#   dgc-prod/integrations/databricks
#   dgc-prod/integrations/teams-hmac
#   dgc-prod/integrations/langsmith-api-key
###############################################################################

variable "name_prefix" { type = string }

###############################################################################
# DB password — auto-generated, used by RDS module
###############################################################################
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.name_prefix}/db/password"
  description             = "RDS PostgreSQL master password"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db.result
}

###############################################################################
# LLM API Keys — placeholder secrets (populate values separately)
###############################################################################
locals {
  placeholder_secrets = {
    "groq-api-key"      = "${var.name_prefix}/llm/groq-api-key"
    "anthropic-api-key" = "${var.name_prefix}/llm/anthropic-api-key"
    "openai-api-key"    = "${var.name_prefix}/llm/openai-api-key"
    "gemini-api-key"    = "${var.name_prefix}/llm/gemini-api-key"
    "langsmith-api-key" = "${var.name_prefix}/integrations/langsmith-api-key"
    "teams-hmac"        = "${var.name_prefix}/integrations/teams-hmac"
  }

  # JSON-structured secrets (ECS reads individual keys from these)
  json_secrets = {
    "jira" = {
      name = "${var.name_prefix}/integrations/jira"
      desc = "Jira REST API credentials {url, user, token, project_key}"
    }
    "collibra" = {
      name = "${var.name_prefix}/integrations/collibra"
      desc = "Collibra REST API credentials {url, username, password}"
    }
    "databricks" = {
      name = "${var.name_prefix}/integrations/databricks"
      desc = "Databricks SQL credentials {host, http_path, token}"
    }
  }
}

resource "aws_secretsmanager_secret" "placeholder" {
  for_each                = local.placeholder_secrets
  name                    = each.value
  description             = "DGC secret: ${each.key} — populate value after deploy"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "placeholder" {
  for_each      = aws_secretsmanager_secret.placeholder
  secret_id     = each.value.id
  secret_string = "REPLACE_ME"

  # Ignore changes so CI/CD can update the value without Terraform overwriting
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "json" {
  for_each                = local.json_secrets
  name                    = each.value.name
  description             = each.value.desc
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "json" {
  for_each  = aws_secretsmanager_secret.json
  secret_id = each.value.id
  secret_string = jsonencode({
    placeholder = "REPLACE_ME — see secret description for required keys"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

###############################################################################
# Outputs
###############################################################################
output "db_password_secret_arn" {
  value = aws_secretsmanager_secret.db_password.arn
}

output "all_secret_arns" {
  description = "All secret ARNs — passed to ECS task definitions"
  value = merge(
    { db_password = aws_secretsmanager_secret.db_password.arn },
    { for k, v in aws_secretsmanager_secret.placeholder : k => v.arn },
    { for k, v in aws_secretsmanager_secret.json : k => v.arn }
  )
}

output "secret_names" {
  description = "Human-readable map of secret names (for documentation)"
  value = merge(
    { db_password = aws_secretsmanager_secret.db_password.name },
    { for k, v in aws_secretsmanager_secret.placeholder : k => v.name },
    { for k, v in aws_secretsmanager_secret.json : k => v.name }
  )
}
