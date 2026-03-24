variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Variable Library will be created."
  type        = string
}

variable "project_prefix" {
  description = "Prefix for resource display names (e.g., 'contoso')."
  type        = string
  default     = "contoso"
}

variable "environment" {
  description = "The deployment environment (dev or prod). Determines variable values."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}
