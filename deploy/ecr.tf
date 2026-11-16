# Preparation only. Do not apply without separate deployment authorization.
terraform {
  required_version = ">= 1.6"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" { region = var.region }
variable "region" { type = string }
resource "aws_ecr_repository" "audit" {
  name = "madmallard-creator-link-audit"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}
output "repository_url" { value = aws_ecr_repository.audit.repository_url }
