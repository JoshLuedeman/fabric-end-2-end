output "workspace_id" {
  description = "The ID of the Fabric Workspace."
  value       = fabric_workspace.this.id
}

output "workspace_name" {
  description = "The display name of the Fabric Workspace."
  value       = fabric_workspace.this.display_name
}
