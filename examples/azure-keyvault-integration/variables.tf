variable "aws_region" {
  description = "AWS region for Secrets Manager resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "secret_name" {
  description = "Name of the secret in AWS Secrets Manager"
  type        = string
}

variable "secret_values" {
  description = "Final resolved secrets (must be injected externally, NOT fetched by Terraform)"
  type        = map(string)
  sensitive   = true
}

variable "kms_key_id" {
  description = "Optional KMS key for encrypting the secret"
  type        = string
  default     = null
}

variable "enable_rotation" {
  description = "Enable automatic secret rotation"
  type        = bool
  default     = false
}

variable "rotation_lambda_arn" {
  description = "Lambda ARN for rotation (required if enable_rotation is true)"
  type        = string
  default     = null
}

variable "rotation_days" {
  description = "Rotation interval in days"
  type        = number
  default     = 30
}

variable "replica_regions" {
  description = "Regions to replicate secret to"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags for AWS resources"
  type        = map(string)
  default     = {}
}
