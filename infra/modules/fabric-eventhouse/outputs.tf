output "eventhouse_id" {
  description = "The ID of the Fabric Eventhouse."
  value       = fabric_eventhouse.this.id
}

output "query_service_uri" {
  description = "The query service URI for the Eventhouse."
  value       = fabric_eventhouse.this.properties.query_service_uri
}

output "ingestion_service_uri" {
  description = "The ingestion service URI for the Eventhouse."
  value       = fabric_eventhouse.this.properties.ingestion_service_uri
}
