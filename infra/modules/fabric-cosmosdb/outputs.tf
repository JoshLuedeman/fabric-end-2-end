# ---------------------------------------------------------------------------
# Outputs — Cosmos DB
#
# These outputs are placeholders until the Fabric Terraform provider adds
# native Cosmos DB support. Uncomment when the real resource is available.
# ---------------------------------------------------------------------------

# output "id" {
#   description = "The Cosmos DB database ID in Fabric."
#   value       = fabric_cosmos_db.this.id
# }

# output "endpoint" {
#   description = "The Cosmos DB endpoint URI for SDK connections."
#   value       = fabric_cosmos_db.this.properties.endpoint
#   sensitive   = true
# }

# output "containers" {
#   description = "Map of container names to their resource IDs."
#   value = {
#     for c in var.containers : c.name => fabric_cosmos_db.this.properties.containers[c.name].id
#   }
# }
