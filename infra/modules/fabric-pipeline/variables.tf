variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Data Pipeline will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Data Pipeline."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Data Pipeline."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the JSON file containing the pipeline definition."
  type        = string
}
