variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Warehouse will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Warehouse."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Warehouse."
  type        = string
  default     = ""
}
