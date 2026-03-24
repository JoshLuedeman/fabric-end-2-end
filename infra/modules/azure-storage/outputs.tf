output "storage_account_id" {
  description = "The ID of the Azure Storage Account."
  value       = azurerm_storage_account.this.id
}

output "primary_blob_endpoint" {
  description = "The primary blob endpoint for the storage account."
  value       = azurerm_storage_account.this.primary_blob_endpoint
}

output "primary_dfs_endpoint" {
  description = "The primary DFS (ADLS Gen2) endpoint for the storage account."
  value       = azurerm_storage_account.this.primary_dfs_endpoint
}

output "storage_account_name" {
  description = "The name of the storage account."
  value       = azurerm_storage_account.this.name
}
