output "mirrored_database_id" {
  description = "The ID of the Fabric Mirrored Database."
  value       = fabric_mirrored_database.this.id
}

output "onelake_tables_path" {
  description = "OneLake path to the mirrored database tables directory."
  value       = fabric_mirrored_database.this.properties.onelake_tables_path
}

output "sql_endpoint_connection_string" {
  description = "The SQL endpoint connection string for querying mirrored data."
  value       = fabric_mirrored_database.this.properties.sql_endpoint_properties.connection_string
  sensitive   = true
}
