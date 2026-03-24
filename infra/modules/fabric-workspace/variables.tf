variable "display_name" {
  description = "The display name of the Fabric Workspace (max 256 characters)."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Workspace."
  type        = string
  default     = ""
}

variable "capacity_id" {
  description = "The ID of the Fabric Capacity to assign to this workspace."
  type        = string
}
