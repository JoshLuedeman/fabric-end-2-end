# ---------------------------------------------------------------------------
# Module: fabric-cosmosdb
# Creates a Cosmos DB database within Microsoft Fabric.
#
# Cosmos DB is available as a workload inside Fabric for NoSQL document
# storage, event sourcing, and operational data serving. It provides
# sub-millisecond reads, automatic indexing, and native integration with
# Fabric analytics (mirroring to OneLake, Spark connector, etc.).
#
# Provider support (as of mid-2025)
# ----------------------------------
# The microsoft/fabric Terraform provider (v1.8) does not yet include a
# dedicated `fabric_cosmos_db` resource. Cosmos DB in Fabric is managed via:
#   1. Fabric portal UI (recommended for initial setup)
#   2. Fabric REST API (POST /v1/workspaces/{id}/cosmosdb)
#   3. Azure CLI / PowerShell
#
# This module uses a placeholder pattern (matching the Change Event Streaming
# approach in fabric-sql-database) so Terraform tracks the intent. When the
# provider adds native support, replace the null_resource with the real
# resource and uncomment the outputs.
#
# Use cases for Contoso Global Retail:
#   - Product catalog (rich, schema-flexible documents with varying attributes)
#   - Customer 360 profiles (aggregated view across POS, web, loyalty)
#   - Order event sourcing (immutable event log for order lifecycle)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Placeholder: create Cosmos DB database via REST API
#
# Uncomment and configure when automating via CI/CD, or replace with a
# native resource when the provider adds support.
#
# resource "null_resource" "cosmos_db" {
#   triggers = {
#     workspace_id = var.workspace_id
#     display_name = var.display_name
#   }
#
#   provisioner "local-exec" {
#     command = <<-EOT
#       az rest --method POST \
#         --url "https://api.fabric.microsoft.com/v1/workspaces/${var.workspace_id}/items" \
#         --headers "Content-Type=application/json" \
#         --body '{
#           "displayName": "${var.display_name}",
#           "description": "${var.description}",
#           "type": "CosmosDB",
#           "definition": {
#             "parts": [
#               {
#                 "path": "cosmosdb-config.json",
#                 "payload": "${base64encode(jsonencode({
#                   "throughputMode": var.throughput_mode,
#                   "defaultConsistencyLevel": var.consistency_level,
#                   "containers": var.containers
#                 }))}"
#               }
#             ]
#           }
#         }'
#     EOT
#   }
# }
# ---------------------------------------------------------------------------

# When the fabric provider adds support, the resource will look like:
#
# resource "fabric_cosmos_db" "this" {
#   display_name = var.display_name
#   description  = var.description
#   workspace_id = var.workspace_id
#
#   configuration = {
#     throughput_mode           = var.throughput_mode
#     default_consistency_level = var.consistency_level
#   }
# }
