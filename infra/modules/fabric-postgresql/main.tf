# ---------------------------------------------------------------------------
# Module: fabric-postgresql
# Creates a PostgreSQL database within Microsoft Fabric.
#
# Fabric PostgreSQL provides open-source PostgreSQL compatibility inside the
# Fabric platform, enabling teams that prefer PostgreSQL's ecosystem (JSON
# operators, PostGIS, extensions) to work natively within Fabric.
#
# Provider support (as of mid-2025)
# ----------------------------------
# The microsoft/fabric Terraform provider (v1.8) does not yet include a
# dedicated `fabric_postgresql` resource. PostgreSQL in Fabric is managed via:
#   1. Fabric portal UI (recommended for initial setup)
#   2. Fabric REST API (POST /v1/workspaces/{id}/postgresql)
#   3. Azure CLI / PowerShell
#
# This module uses a placeholder pattern (matching the Change Event Streaming
# approach in fabric-sql-database) so Terraform tracks the intent. When the
# provider adds native support, replace the null_resource with the real
# resource and uncomment the outputs.
#
# Use case for Tales & Timber:
#   - Marketing analytics database — the marketing team prefers PostgreSQL
#     for its JSON support (campaign metadata) and PostGIS (geo-analysis
#     of campaign reach by store location)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Placeholder: create PostgreSQL database via REST API
#
# Uncomment and configure when automating via CI/CD, or replace with a
# native resource when the provider adds support.
#
# resource "null_resource" "postgresql" {
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
#           "type": "PostgreSQL",
#           "definition": {
#             "parts": [
#               {
#                 "path": "postgresql-config.json",
#                 "payload": "${base64encode(jsonencode({
#                   "version": var.pg_version,
#                   "extensions": var.extensions
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
# resource "fabric_postgresql" "this" {
#   display_name = var.display_name
#   description  = var.description
#   workspace_id = var.workspace_id
#
#   configuration = {
#     version    = var.pg_version
#     extensions = var.extensions
#   }
# }
