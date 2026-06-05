###############################################################################
# Module: IAM
# Roles created:
#   1. ecs_execution_role — ECS pulls images, fetches secrets (used by ECS agent)
#   2. ecs_task_role      — Runtime perms for containers (Bedrock, S3, X-Ray, etc.)
#   3. mwaa_role          — MWAA environment execution role
###############################################################################

variable "name_prefix"  { type = string }
variable "aws_region"   { type = string }
variable "aws_account"  { type = string }

data "aws_caller_identity" "current" {}

###############################################################################
# 1. ECS Execution Role
#    Allows ECS agent to pull ECR images and fetch Secrets Manager / SSM values
###############################################################################
resource "aws_iam_role" "ecs_execution" {
  name = "${var.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "ecs_execution_secrets" {
  name = "${var.name_prefix}-ecs-execution-secrets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account}:secret:${var.name_prefix}/*"
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = "*"
        Condition = {
          StringLike = { "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com" }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_execution_secrets.arn
}

###############################################################################
# 2. ECS Task Role
#    Runtime permissions for the running containers
###############################################################################
resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "ecs_task" {
  name = "${var.name_prefix}-ecs-task-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Bedrock — invoke Claude 3.5 Sonnet (P0: swap from Groq)
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet*",
          "arn:aws:bedrock:${var.aws_region}:${var.aws_account}:provisioned-model/*"
        ]
      },
      # S3 — DAG bucket + ingestion docs
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.name_prefix}-*",
          "arn:aws:s3:::${var.name_prefix}-*/*"
        ]
      },
      # Secrets Manager — runtime reads (e.g. Jira/Collibra tokens)
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account}:secret:${var.name_prefix}/*"
      },
      # X-Ray — distributed tracing (replaces LangSmith SaaS in prod)
      {
        Sid    = "XRayWrite"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      # CloudWatch Logs — structured logging
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account}:log-group:/dgc/*:*"
      },
      # ECS exec (optional but useful for debugging)
      {
        Sid    = "ECSExec"
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task.arn
}

###############################################################################
# 3. MWAA Execution Role
###############################################################################
resource "aws_iam_role" "mwaa" {
  name = "${var.name_prefix}-mwaa-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "airflow.amazonaws.com" }
        Action    = "sts:AssumeRole"
      },
      {
        Effect    = "Allow"
        Principal = { Service = "airflow-env.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_policy" "mwaa" {
  name = "${var.name_prefix}-mwaa-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AirflowS3Access"
        Effect = "Allow"
        Action = ["s3:GetObject*", "s3:GetBucket*", "s3:List*"]
        Resource = [
          "arn:aws:s3:::${var.name_prefix}-mwaa-dags",
          "arn:aws:s3:::${var.name_prefix}-mwaa-dags/*"
        ]
      },
      {
        Sid    = "AirflowLogs"
        Effect = "Allow"
        Action = ["logs:*"]
        Resource = "arn:aws:logs:${var.aws_region}:${var.aws_account}:log-group:airflow-${var.name_prefix}-*"
      },
      {
        Sid    = "AirflowCloudWatch"
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Sid    = "AirflowSQS"
        Effect = "Allow"
        Action = ["sqs:*"]
        Resource = "arn:aws:sqs:${var.aws_region}:*:airflow-celery-*"
      },
      {
        Sid    = "AirflowKMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey*", "kms:Encrypt"]
        Resource = "*"
        Condition = { StringLike = { "kms:ViaService" = ["sqs.${var.aws_region}.amazonaws.com"] } }
      },
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account}:secret:${var.name_prefix}/*"
      },
      # DAGs invoke /ingest on the FastAPI service — allow calling ECS
      {
        Sid    = "ECSRunTask"
        Effect = "Allow"
        Action = ["ecs:RunTask", "ecs:DescribeTasks", "iam:PassRole"]
        Resource = "*"
        Condition = { ArnLike = { "ecs:cluster" = "arn:aws:ecs:${var.aws_region}:${var.aws_account}:cluster/${var.name_prefix}-*" } }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mwaa" {
  role       = aws_iam_role.mwaa.name
  policy_arn = aws_iam_policy.mwaa.arn
}

###############################################################################
# Outputs
###############################################################################
output "ecs_task_role_arn"      { value = aws_iam_role.ecs_task.arn }
output "ecs_execution_role_arn" { value = aws_iam_role.ecs_execution.arn }
output "mwaa_role_arn"          { value = aws_iam_role.mwaa.arn }
