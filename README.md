# Terraform AWS Secrets Manager Module

Reusable Terraform module for creating secure AWS Secrets Manager containers in shared platform environments.

## What This Module Does

✅ Creates empty AWS Secrets Manager containers (infrastructure only)  
✅ Configures encryption, policies, multi-region replication and rotation  
✅ Keeps secrets OUT of Terraform state/logs  
✅ Provides clean container metadata for applications and IAM policies  

## What This Module Does NOT Do

❌ Does NOT manage secret values  
❌ Does NOT inject secret content  
❌ Does NOT integrate with Vault or Key Vault  
❌ Does NOT read from external secret systems  

**Secrets are injected by external systems (CI/CD, Lambda, scripts) AFTER Terraform deployment.**

## Problem Statement

Platform teams often face inconsistent secret management:

- Product teams use raw `aws_secretsmanager_secret` directly
- No consistent encryption, recovery windows, or policies
- Manual IAM management for each secret
- Difficult to enforce compliance and rotation

This module provides a **standardized, reusable infrastructure container** that keeps secrets out of Terraform entirely.

## Key Features

**Infrastructure-only design** — No secret values in Terraform code  
**Zero-secrets architecture** — Nothing sensitive in state or logs  
**KMS encryption** — Optional customer-managed keys  
**Multi-region replication** — Disaster recovery  
**Resource policies** — Cross-account access control  
**External rotation** — Lambda-based, independent of Terraform  
**Safe deletion** — 7-30 day recovery window  

## Quick Start

### Step 1: Create Infrastructure Container

```hcl
module "app_secret" {
  source = "github.com/anjusugathan5/terraform-aws-secrets-manager-module"

  name                    = "shared/platform/app/db"
  description             = "Database credentials"
  recovery_window_in_days = 7

  # Optional
  replica_regions = ["eu-central-1"]
  kms_key_id      = aws_kms_key.this.id

  tags = {
    Environment = "prod"
    Team        = "platform"
  }
}

output "secret_arn" {
  value = module.app_secret.secret_arn
}
Deploy:

bash
terraform init
terraform plan
terraform apply
Result: Empty secret container created. No secrets stored yet.

Step 2: Inject Secrets (External to Terraform)
Choose any method—all run independently of Terraform:

AWS CLI
bash
aws secretsmanager put-secret-value \
  --secret-id shared/platform/app/db \
  --secret-string '{"username":"admin","password":"secure-pass"}'
Lambda Function
Python
import boto3, json

sm = boto3.client('secretsmanager')
sm.put_secret_value(
    SecretId='shared/platform/app/db',
    SecretString=json.dumps({
        "username": "postgres_user",
        "password": "generated-password",
        "host": "db.example.com"
    })
)
CI/CD Pipeline (GitHub Actions)
YAML
name: Inject Secrets
on: [workflow_dispatch]

jobs:
  inject:
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-west-1

      - run: |
          aws secretsmanager put-secret-value \
            --secret-id shared/platform/app/db \
            --secret-string '{"username":"admin","password":"${{ secrets.DB_PASSWORD }}"}'
Kubernetes External Secrets
YAML
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-db-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-sm
    kind: SecretStore
  target:
    name: app-db
  data:
    - secretKey: username
      remoteRef:
        key: shared/platform/app/db
        property: username
Step 3: Applications Retrieve Secrets
Applications read from AWS Secrets Manager after injection:

Python:

Python
import boto3, json

sm = boto3.client('secretsmanager')
secret = sm.get_secret_value(SecretId='shared/platform/app/db')
config = json.loads(secret['SecretString'])

db = connect(host=config['host'], user=config['username'], password=config['password'])
Go:

Go
svc := secretsmanager.New(sess)
result, _ := svc.GetSecretValue(&secretsmanager.GetSecretValueInput{
    SecretId: aws.String("shared/platform/app/db"),
})
var config map[string]string
json.Unmarshal([]byte(*result.SecretString), &config)
Node.js:

JavaScript
const sm = new AWS.SecretsManager();
const secret = await sm.getSecretValue({ SecretId: 'shared/platform/app/db' }).promise();
const config = JSON.parse(secret.SecretString);
Module Inputs
Variable	Type	Default	Required	Description
name	string	-	Yes	Secret name (3+ chars)
description	string	""	No	Human-readable description
kms_key_id	string	null	No	KMS key (default: AWS-managed)
recovery_window_in_days	number	7	No	Recovery window (7-30 days)
enable_rotation	bool	false	No	Enable automatic rotation
rotation_lambda_arn	string	null	No	Lambda ARN for rotation
rotation_days	number	30	No	Rotation interval in days
replica_regions	list(string)	[]	No	Regions to replicate to
resource_policy	string	null	No	JSON resource policy
tags	map(string)	{}	No	Resource tags
Module Outputs
Output	Description
secret_arn	ARN of the secret container
secret_name	Name of the secret container
secret_id	ID of the secret container
kms_key_id	KMS key ID used
replica_regions	List of replica regions
Security Considerations
What This Module PREVENTS
❌ Secrets in Terraform state
❌ Secrets in terraform apply logs
❌ Secrets in terraform plan output
❌ Unencrypted secrets in AWS
Best Practices
Encrypt remote state — Use S3 + KMS or Terraform Cloud
State locking — Use DynamoDB to prevent concurrent applies
IAM access control — Restrict who reads secret containers
KMS encryption — Use customer-managed keys for sensitive data
CloudTrail logging — Audit all secret access
Separate accounts — Different AWS accounts per environment
Examples
examples/basic/ — Infrastructure-only container
examples/post-creation-secret-injection/ — Terraform-injected initial values (external updates allowed)
Deprecated:

examples/azure-keyvault-integration/ — See migration guide in that README
Common Patterns
Pattern 1: Infrastructure Only (Recommended)
bash
# Step 1: Deploy container
terraform apply

# Step 2: Inject secrets externally
aws secretsmanager put-secret-value --secret-id ... --secret-string ...
Pattern 2: With Cross-Account Access
HCL
resource "aws_secretsmanager_secret_policy" "cross_account" {
  secret_arn = module.app_secret.secret_arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { AWS = "arn:aws:iam::OTHER_ACCOUNT:root" }
      Action = "secretsmanager:GetSecretValue"
      Resource = "*"
    }]
  })
}
Pattern 3: With KMS Encryption
HCL
module "app_secret" {
  source = "./"
  name   = "shared/platform/app/db"
  
  kms_key_id = aws_kms_key.secrets.id
}
Pattern 4: Multi-Region Replication
HCL
module "app_secret" {
  source = "./"
  name   = "shared/platform/app/db"
  
  replica_regions = ["eu-west-1", "eu-central-1", "us-east-1"]
}
Pattern 5: Automatic Rotation
HCL
module "app_secret" {
  source = "./"
  name   = "shared/platform/app/db"
  
  enable_rotation     = true
  rotation_lambda_arn = aws_lambda_function.rotate_db_password.arn
  rotation_days       = 30
}
Important: What NOT to Do
❌ Do NOT pass secret values to this module:

HCL
# WRONG - Secrets in Terraform
module "secret" {
  source = "./"
  name   = "my-secret"
  
  secret_values = { password = "secret123" }  # ← NO!
}
❌ Do NOT try to read from Vault/Key Vault in Terraform:

HCL
# WRONG - Terraform reading external systems
data "vault_generic_secret" "db" {
  path = "secret/data/db"
}

module "secret" {
  source = "./"
  secret_values = data.vault_generic_secret.db.data  # ← NO!
}
❌ Do NOT use Azure/Vault data sources:

HCL
# WRONG - External system integration in Terraform
data "azurerm_key_vault_secret" "db" {
  name = "db-password"
  ...
}
Instead: Deploy the module, then inject secrets via external workflow.

Migration Guide
If migrating from another secret system:

Deploy this module for infrastructure
Inject initial secrets using external tool (CLI, Lambda, CI/CD)
Update applications to read from AWS Secrets Manager
Decommission old infrastructure
FAQ
Q: How do I deploy without manual AWS CLI?
A: Use GitHub Actions, Lambda, or any CI/CD pipeline to inject after Terraform.

Q: What if I need secrets during terraform apply?
A: This module doesn't support that by design. Inject secrets as a separate step.

Q: Can I use this with Terraform workspaces?
A: Yes. Use different secret names per workspace and inject accordingly.

Q: Does this support automatic secret generation?
A: No, but pair with AWS Lambda or AWS Systems Manager for generation.

Q: What about secret rotation?
A: Enable enable_rotation and provide a Lambda ARN. Rotation runs independently of Terraform.

Q: Can I inject secrets from Terraform if I want to?
A: Yes, see examples/post-creation-secret-injection/. Use ignore_changes = [secret_string] so external systems can update later.

Testing
bash
# Validate
terraform validate

# Plan
terraform plan

# Deploy container
terraform apply

# Inject a secret
aws secretsmanager put-secret-value \
  --secret-id $(terraform output -raw secret_name) \
  --secret-string '{"test":"value"}'

# Verify
aws secretsmanager describe-secret \
  --secret-id $(terraform output -raw secret_name)
License
MIT
