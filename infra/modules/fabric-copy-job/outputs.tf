output "copy_job_ids" {
  description = "Map of copy job keys to their Fabric resource IDs."
  value       = { for k, v in fabric_copy_job.this : k => v.id }
}
