# ---------------------------------------------------------------------------
# Module: fabric-reflex
# Creates a Microsoft Fabric Reflex (Data Activator) item.
#
# NOTE: As of 2025, there is no dedicated `fabric_reflex` Terraform resource
# in the Microsoft Fabric provider. This module uses the generic
# `fabric_item` resource as a placeholder. When a native resource becomes
# available, migrate to `fabric_reflex` for richer schema support.
#
# Alternative: If `fabric_item` does not yet support Reflex item types in
# your provider version, a `null_resource` with `local-exec` is included
# (commented out) that invokes the Fabric REST API via Azure CLI.
# ---------------------------------------------------------------------------

resource "fabric_item" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
  type         = "Reflex"
  format       = "Default"

  definition = {
    "reflex-content.json" = {
      source = var.definition_path
    }
  }
}

# ---------------------------------------------------------------------------
# Fallback: REST API via Azure CLI (uncomment if fabric_item does not
# support Reflex type in your provider version).
# ---------------------------------------------------------------------------
#
# resource "null_resource" "reflex_via_api" {
#   triggers = {
#     definition_hash = filemd5(var.definition_path)
#     display_name    = var.display_name
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
#           "type": "Reflex",
#           "definition": ${jsonencode({
#             parts = [{
#               path    = "reflex-content.json"
#               payload = filebase64(var.definition_path)
#             }]
#           })}
#         }'
#     EOT
#   }
# }
