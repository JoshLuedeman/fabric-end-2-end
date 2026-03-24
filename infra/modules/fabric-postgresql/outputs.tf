# ---------------------------------------------------------------------------
# Outputs — PostgreSQL
#
# These outputs are placeholders until the Fabric Terraform provider adds
# native PostgreSQL support. Uncomment when the real resource is available.
# ---------------------------------------------------------------------------

# output "id" {
#   description = "The PostgreSQL database ID in Fabric."
#   value       = fabric_postgresql.this.id
# }

# output "connection_string" {
#   description = "PostgreSQL connection string for client connections."
#   value       = fabric_postgresql.this.properties.connection_string
#   sensitive   = true
# }

# output "host" {
#   description = "The PostgreSQL server hostname."
#   value       = fabric_postgresql.this.properties.host
# }

# output "port" {
#   description = "The PostgreSQL server port."
#   value       = fabric_postgresql.this.properties.port
# }
