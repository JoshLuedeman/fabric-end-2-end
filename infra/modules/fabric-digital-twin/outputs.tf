# ---------------------------------------------------------------------------
# Variables for fabric-digital-twin module (placeholder)
# ---------------------------------------------------------------------------
# These variables define the expected interface for when the Terraform
# provider adds support for Digital Twin Builder.
# ---------------------------------------------------------------------------

variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Digital Twin will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Digital Twin."
  type        = string
}

variable "description" {
  description = "The description of the Digital Twin."
  type        = string
  default     = ""
}

variable "model_definition" {
  description = "Path to the JSON file containing the twin model definition."
  type        = string
  default     = ""
}

variable "eventhouse_id" {
  description = "The ID of the Fabric Eventhouse to bind for live telemetry."
  type        = string
  default     = ""
}

variable "kql_database_id" {
  description = "The ID of the KQL Database within the Eventhouse for telemetry queries."
  type        = string
  default     = ""
}
