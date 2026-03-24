variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Semantic Model will be created."
  type        = string
}

variable "display_name" {
  description = "The display name of the Fabric Semantic Model."
  type        = string
}

variable "description" {
  description = "The description of the Fabric Semantic Model."
  type        = string
  default     = ""
}

variable "definition_path" {
  description = "Path to the model.bim (TMSL) definition file."
  type        = string
}

variable "pbism_path" {
  description = "Path to the definition.pbism file."
  type        = string
}
