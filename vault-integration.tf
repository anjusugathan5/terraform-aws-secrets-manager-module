# ============================================================================
# Secret Source Metadata (for tagging & audit only)
# ============================================================================
# NOTE:
# Terraform does NOT fetch secrets from Vault or Azure.
# Secrets must be injected externally into AWS Secrets Manager.
#
# This variable is ONLY for observability and compliance tracking.

locals {
  provisioning_mode = var.use_vault_source ? "vault-external" : (
    var.use_azure_keyvault_source ? "azure-external" : "direct-external"
  )
}
