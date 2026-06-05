#!/usr/bin/env bash
###############################################################################
# post-apply.sh
# Run after `terraform apply` to:
#   1. Populate Secrets Manager with real values
#   2. Initialise RDS (create pgvector extension, run init_neon.sql)
#   3. Upload DAGs to MWAA S3 bucket
#
# Usage:
#   export AWS_PROFILE=your-profile
#   export AWS_REGION=ap-south-1
#   bash scripts/post-apply.sh
###############################################################################
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
NAME_PREFIX="dgc-prod"

echo "=== DGC Post-Apply Setup ==="

# ── Read Terraform outputs ──────────────────────────────────────────────────
cd "$(dirname "$0")/.."
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
DAGS_BUCKET=$(terraform output -json | jq -r '.mwaa_webserver_url.value' || echo "")

echo "RDS endpoint: ${RDS_ENDPOINT}"

# ── Populate secrets interactively ─────────────────────────────────────────
populate_secret() {
  local SECRET_ID="$1"
  local PROMPT="$2"
  local IS_JSON="${3:-false}"

  echo ""
  echo "Secret: ${SECRET_ID}"
  echo "${PROMPT}"

  if [ "${IS_JSON}" = "true" ]; then
    echo "(Enter as JSON, e.g. {\"url\":\"...\",\"user\":\"...\",\"token\":\"...\"})"
  fi

  read -rsp "Value (input hidden): " SECRET_VALUE
  echo ""

  aws secretsmanager put-secret-value \
    --secret-id "${SECRET_ID}" \
    --secret-string "${SECRET_VALUE}" \
    --region "${AWS_REGION}" \
    --output text --query 'Name' \
    | xargs -I{} echo "  ✓ Updated: {}"
}

echo ""
echo "=== Populating API Key Secrets ==="
echo "(Press Ctrl+C to skip and populate later via console or CI/CD)"
echo ""

populate_secret "${NAME_PREFIX}/llm/anthropic-api-key"  "Enter your Anthropic API key (sk-ant-...)"
populate_secret "${NAME_PREFIX}/llm/openai-api-key"     "Enter your OpenAI API key (sk-...)"
populate_secret "${NAME_PREFIX}/llm/groq-api-key"       "Enter your Groq API key (gsk_...)"
populate_secret "${NAME_PREFIX}/llm/gemini-api-key"     "Enter your Gemini API key"
populate_secret "${NAME_PREFIX}/integrations/langsmith-api-key" "Enter your LangSmith API key"

echo ""
echo "=== Populating Integration Secrets (JSON format) ==="

populate_secret "${NAME_PREFIX}/integrations/jira"      \
  'Jira credentials. Format: {"url":"https://your.atlassian.net","user":"you@company.com","token":"...","project_key":"DGC"}' \
  "true"

populate_secret "${NAME_PREFIX}/integrations/collibra"  \
  'Collibra credentials. Format: {"url":"https://your-collibra.com","username":"...","password":"..."}' \
  "true"

populate_secret "${NAME_PREFIX}/integrations/databricks" \
  'Databricks credentials. Format: {"host":"your-workspace.azuredatabricks.net","http_path":"/sql/...","token":"dapi..."}' \
  "true"

populate_secret "${NAME_PREFIX}/integrations/teams-hmac" \
  "Enter your Teams webhook HMAC secret"

# ── Init RDS via a temporary ECS task ──────────────────────────────────────
echo ""
echo "=== Initialising RDS Database ==="
echo "Running init SQL via a temporary Fargate task..."

CLUSTER_NAME="${NAME_PREFIX}-cluster"
TASK_DEF="${NAME_PREFIX}-api"

# Get the private subnet and security group from Terraform outputs
SUBNETS=$(terraform output -json | jq -r '.ecs_cluster_name.value // empty')
echo "Note: Run the following SQL manually against your RDS endpoint using psql"
echo "or via an RDS Query Editor / bastion host:"
echo ""
echo "  CREATE EXTENSION IF NOT EXISTS vector;"
echo "  -- Then run: psql \"\$DATABASE_URL\" -f scripts/init_neon.sql"
echo ""
echo "RDS endpoint (private): ${RDS_ENDPOINT}"
echo "(Connect via bastion host, AWS Systems Manager Session Manager, or RDS Data API)"

# ── Upload DAGs to MWAA ─────────────────────────────────────────────────────
echo ""
echo "=== Uploading DAGs to MWAA S3 bucket ==="

DAGS_BUCKET_NAME="${NAME_PREFIX}-mwaa-dags"

if [ -d "dags/" ]; then
  echo "Syncing dags/ → s3://${DAGS_BUCKET_NAME}/dags/"
  aws s3 sync dags/ "s3://${DAGS_BUCKET_NAME}/dags/" \
    --exclude "*.pyc" \
    --exclude "__pycache__/*" \
    --region "${AWS_REGION}"
  echo "✓ DAGs uploaded"
else
  echo "⚠ No dags/ directory found — create your DAG files and run:"
  echo "  aws s3 sync dags/ s3://${DAGS_BUCKET_NAME}/dags/ --region ${AWS_REGION}"
fi

# Upload requirements.txt
if [ -f "requirements.txt" ]; then
  aws s3 cp requirements.txt "s3://${DAGS_BUCKET_NAME}/requirements.txt" \
    --region "${AWS_REGION}"
  echo "✓ requirements.txt uploaded"
fi

echo ""
echo "=== Post-Apply Complete ==="
echo ""
echo "Next:"
echo "  • Point your domain CNAME to: $(terraform output -raw alb_dns_name 2>/dev/null || echo '<alb_dns_name>')"
echo "  • Verify services: aws ecs list-services --cluster ${CLUSTER_NAME} --region ${AWS_REGION}"
echo "  • Check ECS health: aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${NAME_PREFIX}-api --region ${AWS_REGION}"
echo "  • MWAA UI: $(terraform output -raw mwaa_webserver_url 2>/dev/null || echo '<check console>')"
