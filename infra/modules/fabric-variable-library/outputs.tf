# NOTE: This output returns a placeholder ID until a dedicated
# fabric_variable_library resource is available in the provider.

output "variable_library_id" {
  description = "The ID of the Variable Library (placeholder until native provider support)."
  value       = terraform_data.variable_library.id
}

output "variables" {
  description = "The resolved variable map for this environment."
  value       = local.all_variables
}
