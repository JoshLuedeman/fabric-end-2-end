# ---------------------------------------------------------------------------
# Module: fabric-data-agent
# Creates a Fabric Data Agent.
#
# NOTE: The Data Agent is a FabCon 2026 GA feature. As of provider v1.8.0,
# there is no dedicated "fabric_data_agent" resource. This module uses the
# generic "fabric_item" resource as a placeholder. When a dedicated resource
# becomes available in a future provider version, migrate to it.
#
# If fabric_item is not available in your provider version, you may need to
# manage this resource via the Fabric REST API outside of Terraform until
# native support is added.
# ---------------------------------------------------------------------------

# Placeholder using lifecycle ignore to prevent drift until native support.
# Uncomment and adjust when fabric_item or fabric_data_agent is available.
#
# resource "fabric_item" "data_agent" {
#   display_name = var.display_name
#   description  = var.description
#   workspace_id = var.workspace_id
#   type         = "DataAgent"
# }

# Temporary: Use a null_resource as a placeholder that documents the intent.
# Replace with the real resource when provider support is available.
resource "terraform_data" "data_agent_placeholder" {
  input = {
    display_name = var.display_name
    description  = var.description
    workspace_id = var.workspace_id
    note         = "Placeholder for Fabric Data Agent. Replace with fabric_item or dedicated resource when available."
  }
}
