terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "azurerm" {
  features {}

  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
}

# ============================================================
# IMPORTANT: Secrets are fetched OUTSIDE Terraform module
# This can be CI/CD, script, or external system
# ============================================================

data "external" "azure_secrets" {
  program = ["bash", "${path.module}/scripts/fetch-azure-secrets.sh"]

  query = {
    key_vault_name = var.azure_keyvault_name
    secret_name    = var.azure_secret_name
  }
}

locals {
  # Secrets are already resolved externally
  # Terraform NEVER directly reads Key Vault secrets
  app_secrets = jsondecode(data.external.azure_secrets.result.secrets)

  tags = {
    Environment = var.environment
    Team        = "platform"
    Source      = "azure-keyvault-external"
  }
}

# ============================================================
# AWS Secrets Manager Module (INFRASTRUCTURE ONLY)
# ============================================================
module "app_secret" {
  source = "../../"

  name        = var.secret_name
  description = "Secrets injected externally into AWS Secrets Manager"

  # Only receives final resolved secrets
  secret_values = local.app_secrets

  replica_regions = [
    "eu-central-1",
    "eu-west-2"
  ]

  kms_key_id              = var.kms_key_id
  recovery_window_in_days = 7

  enable_rotation     = var.enable_rotation
  rotation_lambda_arn = var.rotation_lambda_arn
  rotation_days       = var.rotation_days

  tags = local.tags
}

# ============================================================
# OUTPUTS
# ============================================================
output "secret_arn" {
  description = "AWS Secrets Manager secret ARN"
  value       = module.app_secret.secret_arn
}

output "secret_name" {
  description = "AWS Secrets Manager secret name"
  value       = module.app_secret.secret_name
}

output "provisioning_mode" {
  description = "External provisioning mode (metadata only)"
  value       = module.app_secret.provisioning_mode
}
