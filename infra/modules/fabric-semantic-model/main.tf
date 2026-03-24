# ---------------------------------------------------------------------------
# Module: fabric-semantic-model
# Creates a Microsoft Fabric Semantic Model with TMSL definition.
# ---------------------------------------------------------------------------

resource "fabric_semantic_model" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  format       = "TMSL"

  definition = {
    "model.bim" = {
      source = var.definition_path
    }
    "definition.pbism" = {
      source = var.pbism_path
    }
  }
}
