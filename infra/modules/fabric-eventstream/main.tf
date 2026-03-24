# ---------------------------------------------------------------------------
# Module: fabric-eventstream
# Creates a Microsoft Fabric Eventstream.
# ---------------------------------------------------------------------------

resource "fabric_eventstream" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}
