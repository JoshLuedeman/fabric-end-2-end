output "pipeline_id" {
  description = "The ID of the Fabric Deployment Pipeline."
  value       = fabric_deployment_pipeline.this.id
}

output "stage_ids" {
  description = "Map of stage display names to their IDs."
  value = {
    for stage in fabric_deployment_pipeline.this.stages : stage.display_name => stage.id
  }
}
