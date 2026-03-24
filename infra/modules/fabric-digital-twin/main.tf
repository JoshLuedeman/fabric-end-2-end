# ---------------------------------------------------------------------------
# Module: fabric-digital-twin
# Placeholder for Microsoft Fabric Digital Twin Builder.
# ---------------------------------------------------------------------------
# STATUS: Digital Twin Builder is in Preview and does NOT yet have a
#         Terraform resource in the microsoft/fabric provider (~> 1.8).
#
# When a resource becomes available (e.g., fabric_digital_twin), replace the
# commented block below with the real resource definition.
#
# Tracked upstream:
#   https://github.com/microsoft/terraform-provider-fabric/issues
# ---------------------------------------------------------------------------

# resource "fabric_digital_twin" "this" {
#   display_name = var.display_name
#   description  = var.description
#   workspace_id = var.workspace_id
#
#   # Twin model definition (JSON)
#   model_definition = var.model_definition
#
#   # Eventhouse telemetry binding
#   eventhouse_binding {
#     eventhouse_id   = var.eventhouse_id
#     kql_database_id = var.kql_database_id
#   }
# }
