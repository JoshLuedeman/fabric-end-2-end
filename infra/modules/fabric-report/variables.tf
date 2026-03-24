variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Report will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Report."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Report."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the report.json definition file."
  type        = string
}

variable "pbir_path" {
  description = "Path to the definition.pbir file."
  type        = string
}
