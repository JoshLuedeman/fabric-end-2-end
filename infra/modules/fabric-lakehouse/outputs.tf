output "lakehouse_id" {
  description = "The ID of the Fabric Lakehouse."
  value       = fabric_lakehouse.this.id
}

output "sql_endpoint_connection_string" {
  description = "The SQL endpoint connection string for the Lakehouse."
  value       = fabric_lakehouse.this.properties.sql_endpoint_properties.connection_string
}

output "onelake_files_path" {
  description = "OneLake path to the Lakehouse files directory."
  value       = fabric_lakehouse.this.properties.onelake_files_path
}

output "onelake_tables_path" {
  description = "OneLake path to the Lakehouse tables directory."
  value       = fabric_lakehouse.this.properties.onelake_tables_path
}
