output "capacity_id" {
  description = "The ID of the Fabric Capacity."
  value       = azurerm_fabric_capacity.this.id
}

output "capacity_name" {
  description = "The name of the Fabric Capacity."
  value       = azurerm_fabric_capacity.this.name
}
