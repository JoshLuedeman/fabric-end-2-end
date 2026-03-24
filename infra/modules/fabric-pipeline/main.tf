# ---------------------------------------------------------------------------
# Module: fabric-pipeline
# Creates a Microsoft Fabric Data Pipeline.
# ---------------------------------------------------------------------------

resource "fabric_data_pipeline" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  format       = "Default"

  definition = {
    "pipeline-content.json" = {
      source = var.definition_path
    }
  }
}
