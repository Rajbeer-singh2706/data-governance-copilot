# Data Governance Copilot — Terraform IaC

Production AWS infrastructure for the DGC application stack.

## Architecture

```
Internet
  │
  ▼
┌──────────────────────────────────────┐
│  ALB (HTTPS/443) + WAF v2            │
│  - Path /ui/*      → Streamlit app   │
│  - Path /mcp/*     → MCP SSE server  │
│  - Default         → FastAPI         │
└──────────┬───────────────────────────┘
           │ (private subnets)
           ▼
┌──────────────────────────────────────┐
│  ECS Fargate Cluster                 │
│  ┌──────────┐ ┌──────┐ ┌─────────┐  │
│  │  API     │ │ App  │ │  MCP    │  │
│  │ FastAPI  │ │ STlit│ │ Server  │  │
│  │ :8000    │ │ :8501│ │ :8002   │  │
│  └────┬─────┘ └──────┘ └─────────┘  │
└───────┼──────────────────────────────┘
        │
   ┌────┴────────────────────┐
   │                         │
   ▼                         ▼
┌──────────────┐    ┌─────────────────┐
│ RDS Postgres │    │ ElastiCache     │
│ 16 + pgvector│    │ Redis 7 (TLS)   │
│ Multi-AZ     │    │ Primary+Replica │
└──────────────┘    └─────────────────┘

┌──────────────────────────────────────┐
│  MWAA (Managed Airflow 2.9)          │
│  DAGs in S3, metadata in RDS         │
└──────────────────────────────────────┘
```

## Module Map

| Module | Purpose |
|--------|---------|
| `vpc` | VPC, subnets (3 AZ), NAT GW, VPC endpoints (ECR, S3, Secrets Manager, Bedrock) |
| `ecr` | ECR repos for `api`, `app`, `mcp_server` — immutable tags, lifecycle policies |
| `iam` | ECS execution role, ECS task role (Bedrock+S3+X-Ray), MWAA role |
| `secrets` | Secrets Manager — DB password (auto-generated) + all API key placeholders |
| `rds` | PostgreSQL 16 + pgvector, Multi-AZ, gp3, encrypted, Performance Insights |
| `elasticache` | Redis 7 replication group, TLS, AUTH token, LRU eviction |
| `alb` | ALB + WAF v2 (OWASP CRS + rate limit 1000 req/5min), HTTPS, access logs |
| `ecs` | Fargate cluster, 3 task defs, CloudWatch logs, CPU/memory autoscaling |
| `mwaa` | MWAA environment, DAGs S3 bucket, existing DAGs compatible without changes |

## Prerequisites

- Terraform >= 1.6
- AWS CLI configured with permissions to create the above resources
- An ACM certificate for your domain in `ap-south-1`

## First-Time Setup

```bash
# 1. Create S3 backend + DynamoDB lock table
export AWS_PROFILE=your-profile
export AWS_REGION=ap-south-1
bash scripts/bootstrap.sh

# 2. Initialise Terraform
terraform init

# 3. Edit your config
cp environments/prod/terraform.tfvars terraform.tfvars
# Fill in: aws_account_id, acm_certificate_arn

# 4. Plan
terraform plan -var-file=terraform.tfvars

# 5. Apply (~15-20 min, MWAA takes longest)
terraform apply -var-file=terraform.tfvars

# 6. Populate secrets + init DB + upload DAGs
bash scripts/post-apply.sh
```

## P0 Config Switches (already wired into ECS task defs)

These env vars are set automatically in the ECS task definitions:

| Variable | Dev | Prod (this Terraform) |
|----------|-----|----------------------|
| `ENABLE_MOCK` | `true` | `false` |
| `ENVIRONMENT` | `development` | `production` |
| `LLM_PROVIDER` | `groq` | `bedrock` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `MEMORY_BACKEND` | `MemorySaver` | `postgres` |
| `REDIS_ENABLED` | `false` | `true` |
| `REDIS_TLS` | `false` | `true` |
| `TRANSPORT` | `stdio` | `sse` |
| `USE_MCP` | `false` | `true` |

## After Apply — DNS Setup

```bash
# Get ALB DNS name
terraform output alb_dns_name

# Create CNAME in your DNS provider:
#   api.yourdomain.com  →  <alb_dns_name>
```

## Populate Secrets (if skipping post-apply.sh)

```bash
# Anthropic API key (Bedrock cross-region still needs this as fallback)
aws secretsmanager put-secret-value \
  --secret-id dgc-prod/llm/anthropic-api-key \
  --secret-string "sk-ant-..." \
  --region ap-south-1

# Jira (JSON)
aws secretsmanager put-secret-value \
  --secret-id dgc-prod/integrations/jira \
  --secret-string '{"url":"https://your.atlassian.net","user":"you@company.com","token":"...","project_key":"DGC"}' \
  --region ap-south-1

# Repeat for: collibra, databricks, groq-api-key, openai-api-key, teams-hmac
```

## Initialise RDS pgvector

Connect via bastion or Systems Manager Session Manager:

```bash
# Option A: SSM port forwarding to RDS
aws ssm start-session \
  --target <bastion-instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "host=<rds-endpoint>,portNumber=5432,localPortNumber=5432"

# Then in another terminal:
psql "postgresql://dgcadmin:<password>@localhost:5432/dgc?sslmode=require" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"

psql "postgresql://dgcadmin:<password>@localhost:5432/dgc?sslmode=require" \
  -f scripts/init_neon.sql
```

## Useful Commands

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster dgc-prod-cluster \
  --services dgc-prod-api dgc-prod-app dgc-prod-mcp_server \
  --region ap-south-1

# ECS Exec into a running container (for debugging)
aws ecs execute-command \
  --cluster dgc-prod-cluster \
  --task <task-id> \
  --container api \
  --command "/bin/sh" \
  --interactive \
  --region ap-south-1

# View API logs
aws logs tail /dgc/dgc-prod/api --follow --region ap-south-1

# Force new ECS deployment (after ECR push)
aws ecs update-service \
  --cluster dgc-prod-cluster \
  --service dgc-prod-api \
  --force-new-deployment \
  --region ap-south-1
```

## Cost Estimate (ap-south-1, ~720 hrs/month)

| Service | Config | Est. USD/month |
|---------|--------|---------------|
| ECS Fargate (api ×2) | 1 vCPU / 2GB | ~$35 |
| ECS Fargate (app, mcp) | 0.5 vCPU / 1GB each | ~$17 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ | ~$80 |
| ElastiCache Redis | cache.t3.micro ×2 | ~$25 |
| ALB | - | ~$20 |
| MWAA | mw1.small | ~$150 |
| NAT Gateway | ~10GB/month | ~$10 |
| Secrets Manager | ~15 secrets | ~$3 |
| **Total** | | **~$340/month** |

> MWAA dominates cost. For staging, use self-managed Airflow on a single ECS task (~$15/month).

## Teardown

```bash
# Disable deletion protection first
terraform apply -var-file=terraform.tfvars \
  -var="db_instance_class=db.t3.medium" \
  # Edit rds module: deletion_protection = false

terraform destroy -var-file=terraform.tfvars
```
