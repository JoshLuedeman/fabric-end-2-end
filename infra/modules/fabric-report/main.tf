# ---------------------------------------------------------------------------
# Module: fabric-report
# Creates a Microsoft Fabric Report with PBIR-Legacy definition.
# ---------------------------------------------------------------------------

resource "fabric_report" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  format       = "PBIR-Legacy"

  definition = {
    "report.json" = {
      source = var.definition_path
    }
    "definition.pbir" = {
      source = var.pbir_path
    }
  }
}
