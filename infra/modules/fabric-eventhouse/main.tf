# ---------------------------------------------------------------------------
# Module: fabric-eventhouse
# Creates a Microsoft Fabric Eventhouse.
# ---------------------------------------------------------------------------

resource "fabric_eventhouse" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}
