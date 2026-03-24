# ---------------------------------------------------------------------------
# Module: fabric-notebook
# Creates a Microsoft Fabric Notebook with an ipynb definition.
# ---------------------------------------------------------------------------

resource "fabric_notebook" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  format       = "ipynb"

  definition = {
    "notebook-content.ipynb" = {
      source = var.definition_path
    }
  }
}
