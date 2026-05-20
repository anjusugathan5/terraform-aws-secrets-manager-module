provider "aws" {
  region = "eu-west-1"
}

module "app_secret" {
  source = "../../"

  name        = "shared/platform/app/db"
  description = "Application database credentials"

  replica_regions = [
    "eu-central-1"
  ]

  recovery_window_in_days = 7

  tags = {
    Environment = "prod"
    Team        = "platform"
  }
}

output "secret_arn" {
  description = "ARN of the secret container"
  value       = module.app_secret.secret_arn
}

output "secret_name" {
  description = "Name of the secret container"
  value       = module.app_secret.secret_name
}

output "secret_id" {
  description = "ID of the secret container"
  value       = module.app_secret.secret_id
}