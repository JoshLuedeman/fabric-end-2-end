output "dataflow_ids" {
  description = "Map of dataflow keys to their Fabric resource IDs."
  value       = { for k, v in fabric_dataflow.this : k => v.id }
}
