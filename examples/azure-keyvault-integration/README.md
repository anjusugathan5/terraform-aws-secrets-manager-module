# ⚠️ DEPRECATED: Azure Key Vault Integration Example

This example is **deprecated** and no longer reflects the module's architecture. The module now follows an **infrastructure-only pattern** where secret values are injected externally.

## Migration Path

If you're using this example, migrate to one of these patterns:

### Option 1: External Secret Fetch → Inject (Recommended)

Use a **separate workflow** to fetch from Azure Key Vault and inject into AWS Secrets Manager:

```bash
#!/bin/bash
# fetch-and-inject.sh

# Step 1: Fetch secret from Azure Key Vault
SECRET_VALUE=$(az keyvault secret show \
  --vault-name "my-vault" \
  --name "app-credentials" \
  --query value -o tsv)

# Step 2: Inject into AWS Secrets Manager (created by Terraform module)
aws secretsmanager put-secret-value \
  --secret-id shared/platform/app/db \
  --secret-string "$SECRET_VALUE"
```

Run this **after** Terraform deploys the module:
```bash
terraform apply
./fetch-and-inject.sh
```

### Option 2: GitHub Actions Workflow

```yaml
name: Deploy and Inject Secrets

on: [workflow_dispatch]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      # Step 1: Deploy infrastructure with Terraform
      - uses: actions/checkout@v3
      - uses: hashicorp/setup-terraform@v2
      - run: terraform apply -auto-approve

      # Step 2: Fetch from Azure and inject into AWS
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Fetch and inject secrets
        run: |
          SECRET=$(az keyvault secret show \
            --vault-name "${{ secrets.AZURE_VAULT_NAME }}" \
            --name "app-credentials" \
            --query value -o tsv)
          
          aws secretsmanager put-secret-value \
            --secret-id shared/platform/app/db \
            --secret-string "$SECRET"
```

### Option 3: Lambda-Based Sync

Create a Lambda that periodically syncs secrets from Azure to AWS:

```python
import boto3
import json
import requests
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient

def lambda_handler(event, context):
    # Auth with Azure
    credential = ClientSecretCredential(
        tenant_id=os.getenv('AZURE_TENANT_ID'),
        client_id=os.getenv('AZURE_CLIENT_ID'),
        client_secret=os.getenv('AZURE_CLIENT_SECRET')
    )
    
    vault_url = f"https://{os.getenv('AZURE_VAULT_NAME')}.vault.azure.net"
    client = SecretClient(vault_url=vault_url, credential=credential)
    
    # Fetch from Azure
    secret = client.get_secret("app-credentials")
    
    # Inject to AWS
    sm = boto3.client('secretsmanager')
    sm.put_secret_value(
        SecretId='shared/platform/app/db',
        SecretString=secret.value
    )
    
    return {"statusCode": 200}
```

## Why This Change?

The old pattern mixed concerns:
- ❌ Terraform reading from external systems (not idempotent)
- ❌ Module handling secret values (outside module scope)
- ❌ Tight coupling to Azure/Vault (reduces reusability)
- ❌ Secrets in Terraform logs

The new pattern:
- ✅ Infrastructure-only Terraform module
- ✅ External systems manage secret values
- ✅ Secrets never in Terraform state
- ✅ Clear separation of concerns

## See Also

- `examples/basic/` — Simple infrastructure-only deployment
- `examples/post-creation-secret-injection/` — Recommended pattern for injecting values
- Module README — Complete documentation

## Questions?

If you have Azure Key Vault secrets to manage:
1. Deploy the Terraform module (infrastructure only)
2. Use one of the patterns above to inject secrets
3. Track secret versions in your CI/CD system

This approach is more robust, auditable, and follows infrastructure-as-code best practices.
