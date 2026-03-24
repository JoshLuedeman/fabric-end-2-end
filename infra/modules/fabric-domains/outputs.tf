# NOTE: These outputs return placeholder IDs until a dedicated fabric_domain
# resource is available in the provider. Replace with real resource IDs when
# the provider adds native support.

output "domain_ids" {
  description = "Map of domain keys to their placeholder IDs."
  value       = { for key, domain in terraform_data.domain : key => domain.id }
}

output "domain_definitions" {
  description = "The full domain definitions including workspace assignments."
  value       = local.domain_definitions
}
