output "api_id" {
  description = "The ID of the Fabric GraphQL API."
  value       = fabric_graphql_api.this.id
}

output "display_name" {
  description = "The display name of the GraphQL API."
  value       = fabric_graphql_api.this.display_name
}

output "workspace_id" {
  description = "The workspace ID where the GraphQL API is deployed."
  value       = fabric_graphql_api.this.workspace_id
}

output "data_source_id" {
  description = "The data source ID intended for this API (for post-provisioning scripts)."
  value       = var.data_source_id
}

output "endpoint_url" {
  description = <<-EOT
    The GraphQL endpoint URL. Constructed from the workspace and API IDs.
    Format: https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/graphqlApis/{api_id}/graphql
    NOTE: This URL is available after the API is fully configured with a data source.
  EOT
  value       = "https://api.fabric.microsoft.com/v1/workspaces/${fabric_graphql_api.this.workspace_id}/graphqlApis/${fabric_graphql_api.this.id}/graphql"
}
