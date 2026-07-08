###############################################################################
# environments/staging/terraform.tfvars
# Staging: same topology, cheaper instances, no Multi-AZ on RDS
###############################################################################

aws_region     = "ap-south-1"
aws_account_id = "YOUR_ACCOUNT_ID_HERE"
environment    = "staging"

acm_certificate_arn = "arn:aws:acm:ap-south-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERT_ID"

db_instance_class      = "db.t3.micro"
elasticache_node_type  = "cache.t3.micro"
mwaa_environment_class = "mw1.small"
mwaa_max_workers       = 2
