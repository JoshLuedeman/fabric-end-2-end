variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Reflex item will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Reflex (Data Activator) item."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Reflex item."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the JSON file containing the Reflex trigger definition."
  type        = string
}
