###############################################################################
# Module: ECR
# One repository per ECS service with:
#   - Image scanning on push
#   - Lifecycle: keep last 10 tagged, purge untagged after 1 day
#   - Immutable tags in prod
###############################################################################

variable "name_prefix" { type = string }
variable "services"    { type = list(string) }

resource "aws_ecr_repository" "service" {
  for_each             = toset(var.services)
  name                 = "${var.name_prefix}/${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = { Name = "${var.name_prefix}-ecr-${each.value}" }
}

resource "aws_ecr_lifecycle_policy" "service" {
  for_each   = aws_ecr_repository.service
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 tagged images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["v", "sha-"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      }
    ]
  })
}

###############################################################################
# Outputs
###############################################################################
output "repository_urls" {
  description = "Map of service name → ECR repository URL"
  value = {
    for svc, repo in aws_ecr_repository.service : svc => repo.repository_url
  }
}
