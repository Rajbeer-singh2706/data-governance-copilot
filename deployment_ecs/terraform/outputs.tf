###############################################################################
# Root outputs — useful after apply
###############################################################################

output "alb_dns_name" {
  description = "ALB DNS — point your CNAME here"
  value       = module.alb.dns_name
}

output "ecr_repository_urls" {
  description = "ECR repo URLs for each service (use in CI/CD)"
  value       = module.ecr.repository_urls
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "rds_endpoint" {
  description = "RDS writer endpoint (private)"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache primary endpoint (private)"
  value       = module.elasticache.primary_endpoint
  sensitive   = true
}

output "dashboard_url" {
  description = "CloudWatch ops dashboard URL"
  value       = module.monitoring.dashboard_url
}

output "alert_sns_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = module.monitoring.sns_topic_arn
}

output "mwaa_webserver_url" {
  description = "MWAA Airflow UI URL"
  value       = module.mwaa.webserver_url
}

output "secrets_manager_paths" {
  description = "Secrets Manager secret names (for CI/CD and app reference)"
  value       = module.secrets.secret_names
}
