# Post-Creation Secret Injection (Recommended Pattern)

This example demonstrates the **recommended approach** for injecting secrets into AWS Secrets Manager:

1. **Module creates** empty infrastructure container
2. **Terraform injects** initial secrets using `aws_secretsmanager_secret_version`
3. **External systems** can update secrets independently (via `ignore_changes`)

## Key Differences from Basic Example

| Aspect | Basic | This Example |
|--------|-------|--------------|
| Secret injection | External only | Terraform + External |
| Who manages values | CI/CD, Lambda, etc. | Terraform initially, then external |
| Use case | Long-running secrets | Initial setup + external updates |
| `ignore_changes` | N/A | ✅ Yes (allows external overrides) |

## Architecture

```
Step 1: Terraform Apply
    ↓
1. Create aws_secretsmanager_secret (empty)
2. Create aws_secretsmanager_secret_version (with initial values)
    ↓
Step 2: External Systems Can Update
    (Lambda, CI/CD, automation—Terraform won't override)
    ↓
Step 3: Applications Retrieve
```

## Deployment

### 1. Create terraform.tfvars

```hcl
db_username = "postgres_admin"
db_password = "your-secure-password"
db_host     = "db.prod.internal"
db_port     = "5432"
```

Or use environment variables:
```bash
export TF_VAR_db_username="postgres_admin"
export TF_VAR_db_password="your-secure-password"
export TF_VAR_db_host="db.prod.internal"
export TF_VAR_db_port="5432"
```

### 2. Deploy

```bash
cd examples/post-creation-secret-injection
terraform init
terraform plan
terraform apply
```

## Why `ignore_changes`?

The `ignore_changes = [secret_string]` lifecycle rule is **critical**:

```hcl
lifecycle {
  ignore_changes = [secret_string]
}
```

**What this means:**
- ✅ Terraform injects initial secret
- ✅ External systems (Lambda, CI/CD) can update the secret
- ✅ Future `terraform apply` won't revert external changes
- ✅ Secret value stays in sync with external source of truth

**Without this:**
- ❌ External updates would be overridden on next `terraform apply`
- ❌ Terraform becomes the only source of truth (defeats the purpose)

## Updating Secrets (External)

After Terraform deployment, update secrets without touching Terraform:

### Via AWS CLI

```bash
aws secretsmanager put-secret-value \
  --secret-id shared/platform/app/db \
  --secret-string '{
    "username":"postgres_admin",
    "password":"new-password",
    "host":"db.prod.internal",
    "port":"5432"
  }'
```

### Via Lambda

```python
import boto3
import json
import os

sm = boto3.client('secretsmanager')

# Fetch new password from some source
new_password = get_new_password_from_vault()

# Update the secret (Terraform won't override this)
sm.put_secret_value(
    SecretId='shared/platform/app/db',
    SecretString=json.dumps({
        "username": os.getenv('DB_USERNAME'),
        "password": new_password,
        "host": os.getenv('DB_HOST'),
        "port": "5432"
    })
)
```

### Via CI/CD (GitHub Actions)

```yaml
name: Update Database Secret

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  update-secret:
    runs-on: ubuntu-latest
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-west-1

      - name: Rotate database password
        run: |
          NEW_PASSWORD=$(openssl rand -base64 32)
          
          aws secretsmanager put-secret-value \
            --secret-id shared/platform/app/db \
            --secret-string '{
              "username":"postgres_admin",
              "password":"'$NEW_PASSWORD'",
              "host":"db.prod.internal",
              "port":"5432"
            }'
```

## Verifying Changes

```bash
# Check secret metadata
aws secretsmanager describe-secret \
  --secret-id shared/platform/app/db

# Retrieve current secret value
aws secretsmanager get-secret-value \
  --secret-id shared/platform/app/db | jq '.SecretString | fromjson'
```

## Applications Retrieve Secrets

```python
import boto3
import json

sm = boto3.client('secretsmanager')
secret = sm.get_secret_value(SecretId='shared/platform/app/db')
db_config = json.loads(secret['SecretString'])

# Always gets the latest version
db = connect_to_db(
    host=db_config['host'],
    user=db_config['username'],
    password=db_config['password']
)
```

## When to Use This Pattern

✅ Use this example when:
- You need Terraform to inject initial secrets
- External systems will manage secret rotation
- You want separation between infrastructure and value management
- You're migrating from inline secret management

✅ Use the `basic/` example when:
- Secrets are managed entirely externally (CI/CD, Lambda, etc.)
- Terraform should only create the container
- You don't want any secret values in Terraform code

## Security Considerations

1. **Never commit `terraform.tfvars`** — Use environment variables or Terraform Cloud
2. **Encrypt remote state** — S3 + KMS or Terraform Cloud
3. **Use IAM policies** to restrict secret access
4. **Enable CloudTrail** logging for audit trail
5. **Rotate credentials** regularly (see Lambda example above)
6. **Use separate AWS accounts** for different environments

## Comparison: Inline vs. External Injection

### ❌ Don't Do This (Inline Injection)

```hcl
# BAD: Secrets in Terraform code
module "secret" {
  source = "../../"
  name   = "my-secret"
  
  secret_values = {  # ← WRONG: ends up in state file
    password = "secret123"
  }
}
```

### ✅ Do This (Post-Creation Injection)

```hcl
# GOOD: Infrastructure-only, inject after
module "secret" {
  source = "../../"
  name   = "my-secret"
  # No secret_values here!
}

resource "aws_secretsmanager_secret_version" "secret" {
  secret_id     = module.secret.secret_id
  secret_string = jsonencode(var.secret_values)  # From tfvars
  
  lifecycle {
    ignore_changes = [secret_string]  # Allow external updates
  }
}
```

## Cleanup

```bash
terraform destroy
```

This deletes both the secret container and version with a 7-day recovery window.

## Next Steps

- Integrate with **CI/CD for automated secret rotation**
- Add **custom KMS encryption** for additional security
- Use **AWS Lambda** for password generation
- Implement **cross-account access** with resource policies
- See `examples/basic/` for infrastructure-only pattern
