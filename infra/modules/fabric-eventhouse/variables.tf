variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Eventhouse will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Eventhouse."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Eventhouse."
  type        = string
  default     = ""
}
