variable "db_username" {
  description = "Database username (from tfvars or environment)"
  type        = string
  sensitive   = false
  default     = "postgres_admin"
}

variable "db_password" {
  description = "Database password (from tfvars or environment, mark as sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "db_host" {
  description = "Database host"
  type        = string
  default     = "localhost"
}

variable "db_port" {
  description = "Database port"
  type        = string
  default     = "5432"
}