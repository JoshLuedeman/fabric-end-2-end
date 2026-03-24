variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the GraphQL API will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric GraphQL API."
  type        = string
}

variable "description" {
  description = "The description of the Fabric GraphQL API."
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# The following variables capture intent for post-provisioning configuration.
# They are not consumed by the fabric_graphql_api resource directly but are
# passed through as outputs so that downstream automation (GitHub Actions,
# scripts) can complete the data-source binding via the Fabric REST API.
# ---------------------------------------------------------------------------

variable "data_source_id" {
  description = "The ID of the Fabric Warehouse or Lakehouse to expose through the GraphQL API. Used by post-provisioning scripts to bind the data source."
  type        = string
  default     = ""
}

variable "data_source_type" {
  description = "The type of data source: 'warehouse' or 'lakehouse'."
  type        = string
  default     = "warehouse"

  validation {
    condition     = contains(["warehouse", "lakehouse"], var.data_source_type)
    error_message = "data_source_type must be 'warehouse' or 'lakehouse'."
  }
}

variable "schema_path" {
  description = "Path to the GraphQL schema file (.graphql) for documentation and post-provisioning import."
  type        = string
  default     = ""
}
