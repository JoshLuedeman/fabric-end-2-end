# ---------------------------------------------------------------------------
# Outputs — Dev Environment
# ---------------------------------------------------------------------------

# Workspace IDs
output "workspace_ids" {
  description = "Map of workspace area names to their Fabric Workspace IDs."
  value = {
    for area, ws in module.fabric_workspaces : area => ws.workspace_id
  }
}

# Lakehouse IDs
output "lakehouse_ids" {
  description = "Map of lakehouse tier names to their Fabric Lakehouse IDs."
  value = {
    for tier, lh in module.lakehouses : tier => lh.lakehouse_id
  }
}

# Warehouse
output "warehouse_id" {
  description = "The ID of the Contoso data warehouse."
  value       = module.warehouse.warehouse_id
}

output "warehouse_connection_string" {
  description = "The SQL connection string for the Contoso data warehouse."
  value       = module.warehouse.connection_string
  sensitive   = true
}

# Eventhouse
output "eventhouse_id" {
  description = "The ID of the Contoso real-time eventhouse."
  value       = module.eventhouse.eventhouse_id
}

output "kql_database_id" {
  description = "The ID of the Contoso KQL database."
  value       = fabric_kql_database.realtime_db.id
}

# Storage
output "staging_storage_account_id" {
  description = "The ID of the staging storage account."
  value       = module.staging_storage.storage_account_id
}

output "staging_storage_blob_endpoint" {
  description = "The primary blob endpoint of the staging storage account."
  value       = module.staging_storage.primary_blob_endpoint
}

# Capacity
output "capacity_id" {
  description = "The ID of the Fabric Capacity."
  value       = module.fabric_capacity.capacity_id
}
