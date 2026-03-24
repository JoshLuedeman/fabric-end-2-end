# ---------------------------------------------------------------------------
# Module: fabric-copy-job
# Creates Microsoft Fabric Copy Job items.
#
# Copy Jobs provide a simple, scalable way to copy data between stores in
# Fabric — ideal for bulk extract, incremental CDC sync, or scheduled data
# movement without writing pipeline JSON. They run natively in Fabric with
# built-in monitoring.
#
# Provider resource: fabric_copy_job (microsoft/fabric >= 1.8)
# Definition part:   copyjob-content.json
# ---------------------------------------------------------------------------

resource "fabric_copy_job" "this" {
  for_each = var.copy_jobs

  display_name = each.value.display_name
  description  = each.value.description
  workspace_id = var.workspace_id
  format       = "Default"

  definition = {
    "copyjob-content.json" = {
      source = each.value.definition_path
    }
  }
}
