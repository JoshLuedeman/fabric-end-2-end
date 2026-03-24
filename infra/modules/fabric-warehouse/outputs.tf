output "warehouse_id" {
  description = "The ID of the Fabric Warehouse."
  value       = fabric_warehouse.this.id
}

output "connection_string" {
  description = "The SQL connection string for the Warehouse."
  value       = fabric_warehouse.this.properties.connection_string
}
