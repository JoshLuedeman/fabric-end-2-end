# NOTE: This output returns a placeholder ID until a dedicated Fabric Data Agent
# resource is available in the provider. Replace with the real resource ID when
# the provider adds native support.
output "agent_id" {
  description = "The ID of the Fabric Data Agent (placeholder until native provider support)."
  value       = terraform_data.data_agent_placeholder.id
}
