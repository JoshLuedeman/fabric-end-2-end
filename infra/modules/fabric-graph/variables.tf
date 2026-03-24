variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the GraphQL API will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric GraphQL API."
  type        = string
}

variable "description" {
  description = "The description of the Fabric GraphQL API."
  type        = string
  default     = ""
}
