###############################################################################
# Module: ECS
# Fargate cluster + 3 services: api, app, mcp_server
# - Task definitions with Secrets Manager injection
# - CloudWatch log groups (replaces LangSmith SaaS in prod — P2 hardening)
# - Application Auto Scaling per service
# - ECS Exec enabled for debugging
###############################################################################

variable "name_prefix"             { type = string }
variable "aws_region"              { type = string }
variable "aws_account_id"          { type = string }
variable "vpc_id"                  { type = string }
variable "private_subnet_ids"      { type = list(string) }
variable "alb_security_group_id"   { type = string }
variable "target_group_arns"       { type = map(string) }
variable "ecs_task_role_arn"        { type = string }
variable "ecs_execution_role_arn"   { type = string }
variable "ecr_repository_urls"     { type = map(string) }
variable "secrets_arns"            { type = map(string) }
variable "ecs_services"            { type = map(any) }
variable "rds_endpoint"            { type = string }
variable "rds_secret_arn"          { type = string }
variable "redis_endpoint"          { type = string }
variable "rds_db_name"             { type = string }

###############################################################################
# ECS Cluster
###############################################################################
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${var.name_prefix}-ecs-cluster" }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

###############################################################################
# App Security Group — shared by all ECS tasks
###############################################################################
resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app-sg"
  description = "ECS tasks — allow ingress from ALB only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [var.alb_security_group_id]
    description     = "ALB to ECS tasks"
  }

  # Allow tasks to call each other (internal service mesh)
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
    description = "Internal ECS task communication"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-app-sg" }
}

###############################################################################
# CloudWatch Log Groups — one per service (14-day retention)
###############################################################################
resource "aws_cloudwatch_log_group" "service" {
  for_each          = var.ecs_services
  name              = "/dgc/${var.name_prefix}/${each.key}"
  retention_in_days = 14
  tags              = { Service = each.key }
}

###############################################################################
# Common environment variables for all containers
# Secrets injected via `secrets` block (never in env plaintext)
###############################################################################
locals {
  common_env = [
    { name = "ENVIRONMENT",    value = "production" },
    { name = "ENABLE_MOCK",    value = "false" },
    { name = "REDIS_ENABLED",  value = "true" },
    { name = "REDIS_HOST",     value = split(":", var.redis_endpoint)[0] },
    { name = "REDIS_PORT",     value = "6379" },
    { name = "REDIS_TLS",      value = "true" },
    { name = "MEMORY_BACKEND", value = "postgres" },
    { name = "USE_MCP",        value = "true" },
    { name = "LOG_LEVEL",      value = "INFO" },
    { name = "AWS_REGION",     value = var.aws_region },
    # P0: LLM switched to Bedrock
    { name = "LLM_PROVIDER",   value = "bedrock" },
    { name = "LLM_MODEL",      value = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0" },
  ]

  common_secrets = [
    {
      name      = "GROQ_API_KEY"
      valueFrom = var.secrets_arns["groq-api-key"]
    },
    {
      name      = "ANTHROPIC_API_KEY"
      valueFrom = var.secrets_arns["anthropic-api-key"]
    },
    {
      name      = "OPENAI_API_KEY"
      valueFrom = var.secrets_arns["openai-api-key"]
    },
    {
      name      = "LANGSMITH_API_KEY"
      valueFrom = var.secrets_arns["langsmith-api-key"]
    },
  ]

  # DATABASE_URL built from RDS endpoint + secret password
  # Pattern: postgresql://user:pass@host:5432/db?sslmode=require
  # We use a helper container or init script; here we pass components separately
  db_env = [
    { name = "POSTGRES_HOST",    value = split(":", var.rds_endpoint)[0] },
    { name = "POSTGRES_PORT",    value = "5432" },
    { name = "POSTGRES_DB",      value = var.rds_db_name },
    { name = "POSTGRES_USER",    value = "dgcadmin" },
    { name = "POSTGRES_SSLMODE", value = "require" },
  ]

  db_secrets = [
    {
      name      = "POSTGRES_PASSWORD"
      valueFrom = var.rds_secret_arn
    },
  ]
}

###############################################################################
# Task Definitions — one per service
###############################################################################

# API service (FastAPI + uvicorn)
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_services["api"].cpu
  memory                   = var.ecs_services["api"].memory
  task_role_arn            = var.ecs_task_role_arn
  execution_role_arn       = var.ecs_execution_role_arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${var.ecr_repository_urls["api"]}:latest"
    essential = true

    portMappings = [{
      containerPort = var.ecs_services["api"].container_port
      protocol      = "tcp"
    }]

    environment = concat(local.common_env, local.db_env, [
      { name = "TRANSPORT", value = "http" },
    ])

    secrets = concat(local.common_secrets, local.db_secrets, [
      { name = "JIRA_URL",           valueFrom = "${var.secrets_arns["jira"]}:url::" },
      { name = "JIRA_USER",          valueFrom = "${var.secrets_arns["jira"]}:user::" },
      { name = "JIRA_TOKEN",         valueFrom = "${var.secrets_arns["jira"]}:token::" },
      { name = "COLLIBRA_URL",       valueFrom = "${var.secrets_arns["collibra"]}:url::" },
      { name = "COLLIBRA_USERNAME",  valueFrom = "${var.secrets_arns["collibra"]}:username::" },
      { name = "COLLIBRA_PASSWORD",  valueFrom = "${var.secrets_arns["collibra"]}:password::" },
      { name = "DATABRICKS_HOST",    valueFrom = "${var.secrets_arns["databricks"]}:host::" },
      { name = "DATABRICKS_TOKEN",   valueFrom = "${var.secrets_arns["databricks"]}:token::" },
      { name = "TEAMS_HMAC_SECRET",  valueFrom = var.secrets_arns["teams-hmac"] },
    ])

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service["api"].name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = { Service = "api" }
}

# App service (Streamlit UI)
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name_prefix}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_services["app"].cpu
  memory                   = var.ecs_services["app"].memory
  task_role_arn            = var.ecs_task_role_arn
  execution_role_arn       = var.ecs_execution_role_arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = "${var.ecr_repository_urls["app"]}:latest"
    essential = true

    portMappings = [{
      containerPort = var.ecs_services["app"].container_port
      protocol      = "tcp"
    }]

    environment = concat(local.common_env, local.db_env, [
      # Point Streamlit at the internal API service
      { name = "API_BASE_URL", value = "http://api.${var.name_prefix}.local:8000" },
    ])

    secrets = concat(local.common_secrets, local.db_secrets)

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service["app"].name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = { Service = "app" }
}

# MCP Server (SSE transport in prod)
resource "aws_ecs_task_definition" "mcp_server" {
  family                   = "${var.name_prefix}-mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_services["mcp_server"].cpu
  memory                   = var.ecs_services["mcp_server"].memory
  task_role_arn            = var.ecs_task_role_arn
  execution_role_arn       = var.ecs_execution_role_arn

  container_definitions = jsonencode([{
    name      = "mcp-server"
    image     = "${var.ecr_repository_urls["mcp_server"]}:latest"
    essential = true

    portMappings = [{
      containerPort = var.ecs_services["mcp_server"].container_port
      protocol      = "tcp"
    }]

    environment = concat(local.common_env, local.db_env, [
      { name = "TRANSPORT", value = "sse" },
      { name = "MCP_PORT",  value = "8002" },
    ])

    secrets = concat(local.common_secrets, local.db_secrets)

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service["mcp_server"].name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = { Service = "mcp_server" }
}

###############################################################################
# ECS Services
###############################################################################
locals {
  task_definitions = {
    api        = aws_ecs_task_definition.api
    app        = aws_ecs_task_definition.app
    mcp_server = aws_ecs_task_definition.mcp_server
  }
}

resource "aws_ecs_service" "service" {
  for_each = var.ecs_services

  name            = "${var.name_prefix}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = local.task_definitions[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  enable_execute_command = true  # ECS Exec for debugging

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arns[each.key]
    container_name   = each.key == "mcp_server" ? "mcp-server" : each.key
    container_port   = each.value.container_port
  }

  deployment_controller { type = "ECS" }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  lifecycle {
    ignore_changes = [desired_count]  # allow autoscaler to manage count
  }

  tags = { Service = each.key }
}

###############################################################################
# Application Auto Scaling — API service only (Streamlit/MCP scale manually)
###############################################################################
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.service["api"].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name_prefix}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70.0  # scale at 70% CPU
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_appautoscaling_policy" "api_memory" {
  name               = "${var.name_prefix}-api-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 80.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
  }
}

###############################################################################
# Outputs
###############################################################################
output "cluster_name"         { value = aws_ecs_cluster.main.name }
output "cluster_arn"          { value = aws_ecs_cluster.main.arn }
output "app_security_group_id" { value = aws_security_group.app.id }
output "log_group_names" {
  value = { for k, v in aws_cloudwatch_log_group.service : k => v.name }
}
