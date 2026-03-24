variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the PostgreSQL database will be created."
  type        = string
}

variable "display_name" {
  description = "Display name for the PostgreSQL database."
  type        = string
}

variable "description" {
  description = "Description for the PostgreSQL database."
  type        = string
  default     = ""
}

variable "pg_version" {
  description = "PostgreSQL major version."
  type        = string
  default     = "16"

  validation {
    condition     = contains(["14", "15", "16"], var.pg_version)
    error_message = "pg_version must be 14, 15, or 16."
  }
}

variable "extensions" {
  description = "List of PostgreSQL extensions to enable."
  type        = list(string)
  default     = ["postgis", "pg_trgm", "uuid-ossp"]
}
