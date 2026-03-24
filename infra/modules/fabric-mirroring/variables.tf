variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Mirrored Database will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Mirrored Database."
  type        = string
}

variable "description" {
  description = "The description of the Mirrored Database."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the mirroring.json definition file containing mirror configuration."
  type        = string
}
