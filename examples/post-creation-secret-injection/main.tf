provider "aws" {
  region = "eu-west-1"
}

module "app_secret" {
  source = "../../"

  name        = "shared/platform/app/db"
  description = "Application database credentials (injected via Terraform initially)"

  replica_regions = ["eu-central-1"]
  recovery_window_in_days = 7

  tags = {
    Environment = "prod"
    Team        = "platform"
  }
}

# ============================================================
# Initial Secret Injection (Terraform)
# ============================================================
resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = module.app_secret.secret_id

  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_host
    port     = var.db_port
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ============================================================
# OUTPUTS
# ============================================================
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