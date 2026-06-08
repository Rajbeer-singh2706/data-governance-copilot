###############################################################################
# Module: Monitoring
# CloudWatch alarms + dashboard covering ECS, RDS, ElastiCache, ALB
# Replaces LangSmith SaaS observability in prod (P2 hardening)
#
# Alarms fire to an SNS topic → wire to PagerDuty / Slack / email
###############################################################################

variable "name_prefix"      { type = string }
variable "aws_region"       { type = string }
variable "aws_account_id"   { type = string }
variable "ecs_cluster_name" { type = string }
variable "ecs_services"     { type = map(any) }
variable "rds_identifier"   { type = string }
variable "redis_group_id"   { type = string }
variable "alb_arn_suffix"   { type = string }
variable "alert_email"      { type = string; default = "" }

###############################################################################
# SNS Topic for alarm notifications
###############################################################################
resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  tags = { Name = "${var.name_prefix}-alerts" }
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

###############################################################################
# ECS Alarms — one set per service
###############################################################################
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  for_each = var.ecs_services

  alarm_name          = "${var.name_prefix}-${each.key}-cpu-high"
  alarm_description   = "ECS ${each.key} CPU > 85% for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = "${var.name_prefix}-${each.key}"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  for_each = var.ecs_services

  alarm_name          = "${var.name_prefix}-${each.key}-memory-high"
  alarm_description   = "ECS ${each.key} Memory > 90% for 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 90
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = "${var.name_prefix}-${each.key}"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ecs_running_tasks_low" {
  for_each = var.ecs_services

  alarm_name          = "${var.name_prefix}-${each.key}-tasks-low"
  alarm_description   = "ECS ${each.key} running task count < 1"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = "${var.name_prefix}-${each.key}"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

###############################################################################
# RDS Alarms
###############################################################################
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name_prefix}-rds-cpu-high"
  alarm_description   = "RDS CPU > 80% for 10 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  dimensions          = { DBInstanceIdentifier = var.rds_identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rds_connections_high" {
  alarm_name          = "${var.name_prefix}-rds-connections-high"
  alarm_description   = "RDS connection count > 450 (db.t3.medium max ~500)"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 450
  treat_missing_data  = "notBreaching"
  dimensions          = { DBInstanceIdentifier = var.rds_identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage_low" {
  alarm_name          = "${var.name_prefix}-rds-storage-low"
  alarm_description   = "RDS free storage < 5GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120  # 5 GB in bytes
  treat_missing_data  = "notBreaching"
  dimensions          = { DBInstanceIdentifier = var.rds_identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rds_replica_lag" {
  alarm_name          = "${var.name_prefix}-rds-replica-lag"
  alarm_description   = "RDS replica lag > 30 seconds"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 30
  treat_missing_data  = "notBreaching"
  dimensions          = { DBInstanceIdentifier = var.rds_identifier }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

###############################################################################
# ElastiCache Alarms
###############################################################################
resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${var.name_prefix}-redis-cpu-high"
  alarm_description   = "Redis CPU > 70%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 70
  treat_missing_data  = "notBreaching"
  dimensions          = { ReplicationGroupId = var.redis_group_id }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "redis_memory_high" {
  alarm_name          = "${var.name_prefix}-redis-memory-high"
  alarm_description   = "Redis memory usage > 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  dimensions          = { ReplicationGroupId = var.redis_group_id }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${var.name_prefix}-redis-evictions"
  alarm_description   = "Redis evicting keys — cache pressure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Sum"
  threshold           = 1000
  treat_missing_data  = "notBreaching"
  dimensions          = { ReplicationGroupId = var.redis_group_id }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

###############################################################################
# ALB Alarms
###############################################################################
resource "aws_cloudwatch_metric_alarm" "alb_5xx_high" {
  alarm_name          = "${var.name_prefix}-alb-5xx-high"
  alarm_description   = "ALB 5xx errors > 50 in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 50
  treat_missing_data  = "notBreaching"
  dimensions          = { LoadBalancer = var.alb_arn_suffix }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_latency_high" {
  alarm_name          = "${var.name_prefix}-alb-latency-high"
  alarm_description   = "ALB P99 latency > 10 seconds"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  extended_statistic  = "p99"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  dimensions          = { LoadBalancer = var.alb_arn_suffix }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_waf_blocked" {
  alarm_name          = "${var.name_prefix}-waf-block-spike"
  alarm_description   = "WAF blocking > 500 requests in 5 minutes — possible attack"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 500
  treat_missing_data  = "notBreaching"
  dimensions = {
    WebACL = "${var.name_prefix}-waf"
    Region = var.aws_region
    Rule   = "ALL"
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

###############################################################################
# CloudWatch Dashboard
###############################################################################
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-ops"

  dashboard_body = jsonencode({
    widgets = [
      # ── Row 1: ECS ──────────────────────────────────────────────────────
      {
        type   = "metric"
        x = 0; y = 0; width = 8; height = 6
        properties = {
          title  = "ECS CPU Utilization"
          region = var.aws_region
          metrics = [
            for svc in keys(var.ecs_services) : [
              "AWS/ECS", "CPUUtilization",
              "ClusterName", var.ecs_cluster_name,
              "ServiceName", "${var.name_prefix}-${svc}",
              { label = svc }
            ]
          ]
          period = 60
          stat   = "Average"
          yAxis  = { left = { min = 0, max = 100 } }
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 8; y = 0; width = 8; height = 6
        properties = {
          title  = "ECS Memory Utilization"
          region = var.aws_region
          metrics = [
            for svc in keys(var.ecs_services) : [
              "AWS/ECS", "MemoryUtilization",
              "ClusterName", var.ecs_cluster_name,
              "ServiceName", "${var.name_prefix}-${svc}",
              { label = svc }
            ]
          ]
          period = 60
          stat   = "Average"
          yAxis  = { left = { min = 0, max = 100 } }
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 16; y = 0; width = 8; height = 6
        properties = {
          title  = "ALB Request Count + 5xx"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "RequestCount",              "LoadBalancer", var.alb_arn_suffix, { label = "Requests", color = "#2ca02c" }],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", var.alb_arn_suffix, { label = "5xx",      color = "#d62728" }],
          ]
          period = 60
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      # ── Row 2: RDS ──────────────────────────────────────────────────────
      {
        type   = "metric"
        x = 0; y = 6; width = 8; height = 6
        properties = {
          title  = "RDS CPU + Connections"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization",      "DBInstanceIdentifier", var.rds_identifier, { label = "CPU %",       yAxis = "left"  }],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.rds_identifier, { label = "Connections", yAxis = "right" }],
          ]
          period = 60
          stat   = "Average"
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x = 8; y = 6; width = 8; height = 6
        properties = {
          title  = "RDS Read/Write Latency (ms)"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "ReadLatency",  "DBInstanceIdentifier", var.rds_identifier, { label = "Read",  period = 60, stat = "p99" }],
            ["AWS/RDS", "WriteLatency", "DBInstanceIdentifier", var.rds_identifier, { label = "Write", period = 60, stat = "p99" }],
          ]
          period = 60
          stat   = "p99"
          view   = "timeSeries"
        }
      },
      # ── Row 2: Redis ────────────────────────────────────────────────────
      {
        type   = "metric"
        x = 16; y = 6; width = 8; height = 6
        properties = {
          title  = "Redis: Hits, Misses, Evictions"
          region = var.aws_region
          metrics = [
            ["AWS/ElastiCache", "CacheHits",   "ReplicationGroupId", var.redis_group_id, { label = "Hits",      color = "#2ca02c" }],
            ["AWS/ElastiCache", "CacheMisses", "ReplicationGroupId", var.redis_group_id, { label = "Misses",    color = "#ff7f0e" }],
            ["AWS/ElastiCache", "Evictions",   "ReplicationGroupId", var.redis_group_id, { label = "Evictions", color = "#d62728" }],
          ]
          period = 60
          stat   = "Sum"
          view   = "timeSeries"
        }
      },
      # ── Row 3: ALB latency + WAF ─────────────────────────────────────────
      {
        type   = "metric"
        x = 0; y = 12; width = 12; height = 6
        properties = {
          title  = "ALB Target Response Time (p50/p95/p99)"
          region = var.aws_region
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { label = "p50", stat = "p50" }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { label = "p95", stat = "p95" }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { label = "p99", stat = "p99", color = "#d62728" }],
          ]
          period = 60
          view   = "timeSeries"
        }
      },
      {
        type   = "alarm"
        x = 12; y = 12; width = 12; height = 6
        properties = {
          title = "Alarm Status"
          alarms = [
            for svc in keys(var.ecs_services) :
            "arn:aws:cloudwatch:${var.aws_region}:${var.aws_account_id}:alarm:${var.name_prefix}-${svc}-cpu-high"
          ]
        }
      }
    ]
  })
}

###############################################################################
# Log Metric Filters — extract app-level metrics from structured JSON logs
###############################################################################

# Count ERROR-level log lines in API service
resource "aws_cloudwatch_log_metric_filter" "api_errors" {
  name           = "${var.name_prefix}-api-errors"
  log_group_name = "/dgc/${var.name_prefix}/api"
  pattern        = "{ $.level = \"ERROR\" }"

  metric_transformation {
    name      = "APIErrorCount"
    namespace = "DGC/${var.name_prefix}"
    value     = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_error_rate" {
  alarm_name          = "${var.name_prefix}-api-error-rate"
  alarm_description   = "API ERROR log lines > 20 in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "APIErrorCount"
  namespace           = "DGC/${var.name_prefix}"
  period              = 300
  statistic           = "Sum"
  threshold           = 20
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Track LLM guardrail blocks (from structured log field)
resource "aws_cloudwatch_log_metric_filter" "guardrail_blocks" {
  name           = "${var.name_prefix}-guardrail-blocks"
  log_group_name = "/dgc/${var.name_prefix}/api"
  pattern        = "{ $.guardrail_passed = false }"

  metric_transformation {
    name      = "GuardrailBlockCount"
    namespace = "DGC/${var.name_prefix}"
    value     = "1"
    default_value = "0"
  }
}

# Track daily token budget hits
resource "aws_cloudwatch_log_metric_filter" "token_budget_hits" {
  name           = "${var.name_prefix}-token-budget-hits"
  log_group_name = "/dgc/${var.name_prefix}/api"
  pattern        = "\"token budget exceeded\""

  metric_transformation {
    name      = "TokenBudgetHits"
    namespace = "DGC/${var.name_prefix}"
    value     = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "token_budget_alarm" {
  alarm_name          = "${var.name_prefix}-token-budget-exceeded"
  alarm_description   = "Daily LLM token budget hit — review llm_guard.py thresholds"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "TokenBudgetHits"
  namespace           = "DGC/${var.name_prefix}"
  period              = 3600
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

###############################################################################
# Outputs
###############################################################################
output "sns_topic_arn"    { value = aws_sns_topic.alerts.arn }
output "dashboard_name"   { value = aws_cloudwatch_dashboard.main.dashboard_name }
output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}
