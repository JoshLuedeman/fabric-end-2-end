output "id" {
  description = "The SQL Database ID"
  value       = fabric_sql_database.this.id
}

output "connection_string" {
  description = "SQL connection string"
  value       = fabric_sql_database.this.properties.connection_string
  sensitive   = true
}
