variable "workspace_id" {
  description = "The ID of the Fabric Workspace where Dataflow Gen2 items will be created."
  type        = string
}

variable "dataflows" {
  description = <<-EOT
    Map of Dataflow Gen2 definitions to create. Each entry must specify:
    - display_name:  The display name of the dataflow.
    - description:   Optional description.
    - mashup_path:   Path to the Power Query M (.pq) definition file.
    - metadata_path: Path to the queryMetadata.json definition file.
  EOT
  type = map(object({
    display_name  = string
    description   = optional(string, "")
    mashup_path   = string
    metadata_path = string
  }))
}
