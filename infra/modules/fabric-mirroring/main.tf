# ---------------------------------------------------------------------------
# Module: fabric-mirroring
# Creates a Microsoft Fabric Mirrored Database.
#
# Mirroring continuously replicates data from an external database (e.g.,
# Azure SQL, Cosmos DB, Snowflake) into OneLake in near real-time via CDC.
# The mirrored data lands in Delta-Parquet format and is immediately
# queryable via the Lakehouse SQL endpoint.
#
# Provider resource: fabric_mirrored_database (microsoft/fabric >= 1.8)
# Definition part:   mirroring.json
# ---------------------------------------------------------------------------

resource "fabric_mirrored_database" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  format       = "Default"

  definition = {
    "mirroring.json" = {
      source = var.definition_path
    }
  }
}
