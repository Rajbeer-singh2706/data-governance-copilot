###############################################################################
# environments/prod/terraform.tfvars
# Copy this to the repo root or pass with -var-file when applying
###############################################################################

aws_region     = "ap-south-1"
aws_account_id = "YOUR_ACCOUNT_ID_HERE"   # e.g. "123456789012"
environment    = "prod"

# ACM certificate for your domain (must be in ap-south-1)
# Create via: aws acm request-certificate --domain-name api.yourdomain.com --validation-method DNS
acm_certificate_arn = "arn:aws:acm:ap-south-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERT_ID"

# RDS — db.t3.medium for small prod, db.r6g.large for larger workloads
db_instance_class = "db.t3.medium"

# ElastiCache — cache.t3.micro for dev-like prod, cache.r6g.large for heavy use
elasticache_node_type = "cache.t3.micro"

# MWAA — mw1.small handles up to 5 concurrent DAG runs well
mwaa_environment_class = "mw1.small"
mwaa_max_workers       = 5
