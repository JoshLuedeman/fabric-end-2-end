variable "workspace_id" {
  description = "The ID of the Fabric Workspace where Copy Jobs will be created."
  type        = string
}

variable "copy_jobs" {
  description = <<-EOT
    Map of Copy Job definitions to create. Each entry must specify:
    - display_name:    The display name of the copy job.
    - description:     Optional description.
    - definition_path: Path to the copyjob-content.json definition file.
  EOT
  type = map(object({
    display_name    = string
    description     = optional(string, "")
    definition_path = string
  }))
}
