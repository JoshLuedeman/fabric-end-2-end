# ---------------------------------------------------------------------------
# Module: fabric-variable-library
# Provisions Fabric Variable Library groups for environment configuration.
#
# NOTE: As of microsoft/fabric provider v1.8.0, there is no dedicated
# resource for Variable Library. This module uses terraform_data placeholders
# to document the variable configuration intent. When the provider adds
# native support, migrate to the real resource.
#
# Variable Library can be managed via the Fabric REST API:
#   PUT https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/variables
#
# Reference: https://learn.microsoft.com/en-us/fabric/data-engineering/variable-library-overview
# ---------------------------------------------------------------------------

locals {
  # Environment-specific variable values
  environment_variables = {
    LAKEHOUSE_NAME = {
      description = "Display name of the primary gold lakehouse"
      value       = "lh_gold"
      type        = "string"
    }
    WAREHOUSE_NAME = {
      description = "Display name of the central data warehouse"
      value       = "${var.project_prefix}_warehouse"
      type        = "string"
    }
    SQL_DATABASE_NAME = {
      description = "Display name of the OLTP operational SQL database"
      value       = "${var.project_prefix}_operational_db"
      type        = "string"
    }
    DATA_RETENTION_DAYS = {
      description = "Days to retain raw/bronze data before archival"
      value       = var.environment == "prod" ? "365" : "30"
      type        = "integer"
    }
    BATCH_SIZE = {
      description = "Records per batch in pipeline copy activities"
      value       = var.environment == "prod" ? "1000000" : "10000"
      type        = "integer"
    }
    LOG_LEVEL = {
      description = "Logging verbosity for notebooks and pipelines"
      value       = var.environment == "prod" ? "WARNING" : "DEBUG"
      type        = "string"
    }
    REFRESH_SCHEDULE_CRON = {
      description = "Cron expression for scheduled data refresh"
      value       = var.environment == "prod" ? "0 */4 * * *" : "manual"
      type        = "string"
    }
  }

  # Feature flags
  feature_flags = {
    ENABLE_ML_SCORING = {
      description = "Enable real-time ML model scoring in data pipelines"
      value       = var.environment == "prod" ? "false" : "true"
      type        = "boolean"
    }
    ENABLE_REALTIME_DASHBOARD = {
      description = "Enable DirectQuery-based real-time monitoring dashboard"
      value       = "true"
      type        = "boolean"
    }
    ENABLE_DATA_QUALITY_ALERTS = {
      description = "Enable automated data quality checks via Data Activator"
      value       = var.environment == "prod" ? "true" : "false"
      type        = "boolean"
    }
    ENABLE_COST_ALLOCATION = {
      description = "Enable per-department capacity usage tracking"
      value       = var.environment == "prod" ? "true" : "false"
      type        = "boolean"
    }
  }

  # Merge all variables into a single map
  all_variables = merge(local.environment_variables, local.feature_flags)
}

# ---------------------------------------------------------------------------
# Placeholder: fabric_variable_library resources
# Replace with the real resource when provider support is available:
#
# resource "fabric_variable_library" "this" {
#   workspace_id = var.workspace_id
#   display_name = "${var.project_prefix}_variable_library"
#
#   dynamic "variable" {
#     for_each = local.all_variables
#     content {
#       name        = variable.key
#       description = variable.value.description
#       type        = variable.value.type
#       value       = variable.value.value
#     }
#   }
# }
# ---------------------------------------------------------------------------

resource "terraform_data" "variable_library" {
  input = {
    workspace_id = var.workspace_id
    display_name = "${var.project_prefix}_variable_library"
    environment  = var.environment
    variables    = local.all_variables
    note         = "Placeholder for Fabric Variable Library. Provision via REST API or replace with fabric_variable_library resource when available."
  }
}
