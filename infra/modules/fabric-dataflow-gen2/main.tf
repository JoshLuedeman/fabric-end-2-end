# ---------------------------------------------------------------------------
# Module: fabric-dataflow-gen2
# Creates Microsoft Fabric Dataflow Gen2 items.
#
# Dataflow Gen2 provides a low-code data transformation experience using
# Power Query M. Each dataflow contains mashup (M expressions) and query
# metadata that define the transformation logic.
#
# Provider resource: fabric_dataflow (microsoft/fabric >= 1.8)
# Definition parts:  mashup.pq (Power Query M), queryMetadata.json
# ---------------------------------------------------------------------------

resource "fabric_dataflow" "this" {
  for_each = var.dataflows

  display_name = each.value.display_name
  description  = each.value.description
  workspace_id = var.workspace_id
  format       = "Default"

  definition = {
    "mashup.pq" = {
      source = each.value.mashup_path
    }
    "queryMetadata.json" = {
      source = each.value.metadata_path
    }
  }
}
