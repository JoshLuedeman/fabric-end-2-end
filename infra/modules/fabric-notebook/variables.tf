variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Notebook will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Notebook."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Notebook."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the .ipynb file to use as the notebook content definition."
  type        = string
}
