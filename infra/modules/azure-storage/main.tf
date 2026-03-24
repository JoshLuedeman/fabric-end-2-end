# ---------------------------------------------------------------------------
# Module: azure-storage
# Creates an Azure Storage Account with blob containers for staging data.
# ---------------------------------------------------------------------------

resource "azurerm_storage_account" "this" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true # Enable hierarchical namespace for ADLS Gen2

  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false

  tags = var.tags
}

resource "azurerm_storage_container" "this" {
  for_each = toset(var.container_names)

  name               = each.value
  storage_account_id = azurerm_storage_account.this.id
}
