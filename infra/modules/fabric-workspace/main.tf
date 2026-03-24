# ---------------------------------------------------------------------------
# Module: fabric-workspace
# Creates a Microsoft Fabric Workspace.
# ---------------------------------------------------------------------------

resource "fabric_workspace" "this" {
  display_name = var.display_name
  description  = var.description
  capacity_id  = var.capacity_id
}
