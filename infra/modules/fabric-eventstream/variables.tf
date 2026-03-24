variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Eventstream will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Eventstream."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Eventstream."
  type        = string
  default     = ""
}
