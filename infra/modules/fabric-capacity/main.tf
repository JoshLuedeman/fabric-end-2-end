# ---------------------------------------------------------------------------
# Module: fabric-capacity
# Creates an Azure Fabric Capacity (F-SKU) using the azurerm provider.
# ---------------------------------------------------------------------------

resource "azurerm_fabric_capacity" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location

  administration_members = var.admin_members

  sku {
    name = var.sku_name
    tier = "Fabric"
  }

  tags = var.tags
}
