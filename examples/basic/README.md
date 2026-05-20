````markdown
# Basic Example: Infrastructure-Only Secret Container

This example shows the **simplest possible deployment** of the module:
- Provisions an empty secret container only
- No secret values in Terraform code
- KMS encryption enabled
- Multi-region replication
- Outputs for applications and IAM policies

## Architecture

```
Terraform Apply
    ↓
aws_secretsmanager_secret (empty container)
    ↓
External system injects secrets AFTER Terraform
    ↓
Applications retrieve
```

## Key Pattern

**Module creates infrastructure. You manage secrets externally.**

This separation ensures:
- ✅ Secrets never in Terraform state
- ✅ Secrets never in logs or plans
- ✅ External systems control secret lifecycle
- ✅ CI/CD can update without Terraform changes

## Deployment

```bash
cd examples/basic
terraform init
terraform plan
terraform apply
```

## Outputs

After applying:

```hcl
secret_arn  = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:shared/platform/app/db-xxxxx"
secret_name = "shared/platform/app/db"
secret_id   = "shared/platform/app/db"
```

Use these to:
1. **Write IAM policies** allowing apps to read secrets
2. **Inject initial secrets** after deployment
3. **Configure rotations** with Lambda/external systems

## Step 2: Inject Secrets (After Terraform)

The module creates an **empty container**. You populate it using any of these methods:

### Option A: AWS CLI (Manual)

```bash
aws secretsmanager put-secret-value \
  --secret-id shared/platform/app/db \
  --secret-string '{
    "username":"postgres_user",
    "password":"secure-password",
    "host":"db.prod.internal",
    "port":"5432"
  }'
```

### Option B: Lambda Function

```python
import boto3
import json
import os

sm = boto3.client('secretsmanager')

secret = {
    "username": os.getenv('DB_USERNAME'),
    "password": os.getenv('DB_PASSWORD'),
    "host": os.getenv('DB_HOST'),
    "port": "5432"
}

sm.put_secret_value(
    SecretId='shared/platform/app/db',
    SecretString=json.dumps(secret)
)
```

### Option C: CI/CD Pipeline (GitHub Actions)

```yaml
name: Inject Secrets

on: [workflow_dispatch]

jobs:
  inject:
    runs-on: ubuntu-latest
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-west-1

      - name: Inject secrets
        run: |
          aws secretsmanager put-secret-value \
            --secret-id shared/platform/app/db \
            --secret-string '{
              "username":"admin",
              "password":"${{ secrets.DB_PASSWORD }}",
              "host":"db.example.com",
              "port":"5432"
            }'
```

### Option D: Kubernetes External Secrets

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-db-secret
  namespace: default
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-sm
    kind: SecretStore
  target:
    name: app-db
    template:
      engineVersion: v2
  data:
    - secretKey: username
      remoteRef:
        key: shared/platform/app/db
        property: username
    - secretKey: password
      remoteRef:
        key: shared/platform/app/db
        property: password
```

### Option E: Terraform Post-Creation (if needed)

If you want Terraform to inject initial values, use the `post-creation-secret-injection` example instead. It includes `ignore_changes` so external systems can update later.

## Step 3: Applications Retrieve Secrets

Once injected, apps retrieve from AWS Secrets Manager:

### Python

```python
import boto3
import json

sm = boto3.client('secretsmanager')
secret = sm.get_secret_value(SecretId='shared/platform/app/db')
db_config = json.loads(secret['SecretString'])

# Use credentials
db = psycopg2.connect(
    host=db_config['host'],
    user=db_config['username'],
    password=db_config['password'],
    port=db_config['port']
)
```

### Go

```go
import (
    "github.com/aws/aws-sdk-go/service/secretsmanager"
    "encoding/json"
)

svc := secretsmanager.New(sess)
result, _ := svc.GetSecretValue(&secretsmanager.GetSecretValueInput{
    SecretId: aws.String("shared/platform/app/db"),
})
var dbConfig map[string]string
json.Unmarshal([]byte(*result.SecretString), &dbConfig)
```

### Node.js

```javascript
const AWS = require('aws-sdk');
const sm = new AWS.SecretsManager();

const secret = await sm.getSecretValue({
  SecretId: 'shared/platform/app/db'
}).promise();

const dbConfig = JSON.parse(secret.SecretString);
```

## Multi-Region Replication

This example replicates to `eu-central-1`. The container is automatically replicated:

```bash
# View replication status
aws secretsmanager describe-secret \
  --secret-id shared/platform/app/db \
  --query 'ReplicationStatus'
```

Inject the secret in the primary region—it replicates automatically to all configured regions.

## Verify Deployment

```bash
# Check secret exists (no values shown)
aws secretsmanager describe-secret \
  --secret-id shared/platform/app/db

# After injecting secrets, retrieve value
aws secretsmanager get-secret-value \
  --secret-id shared/platform/app/db | jq '.SecretString | fromjson'
```

## Cleanup

```bash
terraform destroy
```

Deletes the secret container with a 7-day recovery window.

## When to Use This Example

✅ Use this when:
- You want infrastructure-only Terraform
- Secrets managed by CI/CD, Lambda, or other external systems
- You need clean separation of concerns

✅ Use `post-creation-secret-injection/` when:
- You want Terraform to inject initial values
- External systems will rotate secrets later
- You need `ignore_changes` for external updates

## Common Patterns

### Pattern 1: Infrastructure First

```bash
# Deploy just the container
terraform apply

# Later: inject secrets via separate workflow
aws secretsmanager put-secret-value ...
```

### Pattern 2: With Cross-Account Access

```hcl
resource "aws_secretsmanager_resource_policy" "this" {
  secret_arn = module.app_secret.secret_arn
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::OTHER_ACCOUNT:root"
      }
      Action   = "secretsmanager:GetSecretValue"
      Resource = "*"
    }]
  })
}
```

### Pattern 3: With Custom KMS Key

```hcl
module "app_secret" {
  source = "../../"
  
  name       = "shared/platform/app/db"
  kms_key_id = aws_kms_key.this.id  # Use custom key instead of default
  
  # ... other config
}
```

### Pattern 4: With Automatic Rotation

```hcl
module "app_secret" {
  source = "../../"
  
  name                = "shared/platform/app/db"
  enable_rotation     = true
  rotation_lambda_arn = aws_lambda_function.rotation.arn
  rotation_days       = 30
  
  # ... other config
}
```

## Next Steps

- Set up **CI/CD for automated secret injection**
- Add **custom KMS encryption** for sensitive environments
- Implement **cross-account access** with resource policies
- Configure **automatic rotation** with Lambda functions
- See `post-creation-secret-injection/` for Terraform-managed initial injection

## Security Best Practices

1. **Never commit secrets** — Use environment variables, Terraform Cloud, or encrypted vaults
2. **Encrypt remote state** — Use S3 + KMS or Terraform Cloud
3. **Use IAM policies** — Restrict who can read secrets
4. **Enable CloudTrail** — Log all secret access
5. **Rotate regularly** — Use Lambda or CI/CD for automated rotation
6. **Use separate AWS accounts** — Production vs. staging
````
