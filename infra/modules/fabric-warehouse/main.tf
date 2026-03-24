# ---------------------------------------------------------------------------
# Module: fabric-warehouse
# Creates a Microsoft Fabric Warehouse.
# ---------------------------------------------------------------------------

resource "fabric_warehouse" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}
