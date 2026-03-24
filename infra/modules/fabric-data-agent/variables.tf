variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Data Agent will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Data Agent."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Data Agent."
  type        = string
  default     = ""
}
