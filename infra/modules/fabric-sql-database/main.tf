# ---------------------------------------------------------------------------
# Module: fabric-sql-database
# Creates a Microsoft Fabric SQL Database (OLTP operational database).
#
# Change Event Streaming
# ----------------------
# The OLTP simulator writes POS transactions, customer interactions, and
# inventory updates directly to this SQL Database.  Fabric SQL Database's
# built-in "Change Event Streaming" feature pushes those changes as CDC
# events to an Eventstream, which routes them to:
#   - Eventhouse (tt_kqldb)  — real-time KQL analytics
#   - Lakehouse  (bronze layer)   — near-real-time batch analytics
#
# This eliminates the need for a separate POS/inventory event generator.
# See: src/eventstream/change_event_config.json for the full routing setup.
# ---------------------------------------------------------------------------

resource "fabric_sql_database" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}

# ---------------------------------------------------------------------------
# Change Event Streaming configuration
#
# As of mid-2025, there is no native Terraform resource for enabling Change
# Event Streaming on a Fabric SQL Database.  The configuration must be done
# via one of:
#   1. Fabric portal UI  (recommended for initial setup)
#   2. Fabric REST API   (POST /v1/workspaces/{id}/sqlDatabases/{id}/changeEventStreaming)
#   3. Azure CLI / PowerShell  (az fabric sql-database update)
#
# When the Terraform Fabric provider adds support, replace the null_resource
# below with a native resource.  The configuration values are kept here so
# Terraform tracks the intent even though it can't enforce it yet.
#
# Tracked tables (monitored for CDC events):
#   - dbo.Transactions
#   - dbo.TransactionItems
#   - dbo.Inventory
#   - dbo.CustomerInteractions
# ---------------------------------------------------------------------------

# Placeholder: enable Change Event Streaming via REST API
# Uncomment and configure when automating via CI/CD.
#
# resource "null_resource" "enable_change_event_streaming" {
#   depends_on = [fabric_sql_database.this]
#
#   triggers = {
#     sql_database_id = fabric_sql_database.this.id
#     eventstream_id  = var.eventstream_id
#     tables_hash     = sha256(join(",", var.change_event_tables))
#   }
#
#   provisioner "local-exec" {
#     command = <<-EOT
#       az rest --method POST \
#         --url "https://api.fabric.microsoft.com/v1/workspaces/${var.workspace_id}/sqlDatabases/${fabric_sql_database.this.id}/changeEventStreaming" \
#         --headers "Content-Type=application/json" \
#         --body '{
#           "eventstream_id": "${var.eventstream_id}",
#           "tables": ${jsonencode([for t in var.change_event_tables : { "schema": "dbo", "table": t }])},
#           "capture_mode": "Incremental"
#         }'
#     EOT
#   }
# }
