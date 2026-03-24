output "adls_gen2_shortcut_ids" {
  description = "Map of ADLS Gen2 shortcut keys to their Fabric resource IDs."
  value       = { for k, v in fabric_shortcut.adls_gen2 : k => v.id }
}

output "onelake_shortcut_ids" {
  description = "Map of OneLake cross-workspace shortcut keys to their Fabric resource IDs."
  value       = { for k, v in fabric_shortcut.onelake : k => v.id }
}
