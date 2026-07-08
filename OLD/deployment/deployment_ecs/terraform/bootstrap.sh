#!/usr/bin/env bash
###############################################################################
# bootstrap.sh
# Run ONCE before `terraform init` to create the S3 backend bucket
# and DynamoDB lock table that Terraform needs for remote state.
#
# Usage:
#   export AWS_PROFILE=your-profile   # or use env vars
#   export AWS_REGION=ap-south-1
#   bash scripts/bootstrap.sh
###############################################################################
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATE_BUCKET="dgc-terraform-state-${ACCOUNT_ID}"
LOCK_TABLE="dgc-terraform-locks"

echo "=== DGC Terraform Bootstrap ==="
echo "Region:       ${AWS_REGION}"
echo "Account:      ${ACCOUNT_ID}"
echo "State bucket: ${STATE_BUCKET}"
echo "Lock table:   ${LOCK_TABLE}"
echo ""

# ── S3 bucket ──────────────────────────────────────────────────────────────
if aws s3api head-bucket --bucket "${STATE_BUCKET}" 2>/dev/null; then
  echo "✓ S3 bucket already exists: ${STATE_BUCKET}"
else
  echo "Creating S3 bucket: ${STATE_BUCKET}"
  if [ "${AWS_REGION}" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "${STATE_BUCKET}" --region "${AWS_REGION}"
  else
    aws s3api create-bucket \
      --bucket "${STATE_BUCKET}" \
      --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}"
  fi

  # Versioning — lets you recover old state files
  aws s3api put-bucket-versioning \
    --bucket "${STATE_BUCKET}" \
    --versioning-configuration Status=Enabled

  # Encryption
  aws s3api put-bucket-encryption \
    --bucket "${STATE_BUCKET}" \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
      }]
    }'

  # Block all public access
  aws s3api put-public-access-block \
    --bucket "${STATE_BUCKET}" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

  echo "✓ S3 bucket created and hardened"
fi

# ── DynamoDB lock table ─────────────────────────────────────────────────────
if aws dynamodb describe-table --table-name "${LOCK_TABLE}" --region "${AWS_REGION}" 2>/dev/null; then
  echo "✓ DynamoDB table already exists: ${LOCK_TABLE}"
else
  echo "Creating DynamoDB table: ${LOCK_TABLE}"
  aws dynamodb create-table \
    --table-name "${LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${AWS_REGION}"

  aws dynamodb wait table-exists --table-name "${LOCK_TABLE}" --region "${AWS_REGION}"
  echo "✓ DynamoDB table created"
fi

# ── Update backend config ───────────────────────────────────────────────────
# Replace the bucket name in main.tf with the account-specific one
sed -i.bak \
  "s|bucket.*= \"dgc-terraform-state\"|bucket         = \"${STATE_BUCKET}\"|" \
  "$(dirname "$0")/../main.tf"

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Update environments/prod/terraform.tfvars with your aws_account_id and acm_certificate_arn"
echo "  2. cd terraform && terraform init"
echo "  3. terraform plan -var-file=environments/prod/terraform.tfvars"
echo "  4. terraform apply -var-file=environments/prod/terraform.tfvars"
echo ""
echo "After apply, populate secrets:"
echo "  aws secretsmanager put-secret-value \\"
echo "    --secret-id dgc-prod/llm/anthropic-api-key \\"
echo "    --secret-string 'sk-ant-...'"
