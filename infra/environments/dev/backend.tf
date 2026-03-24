terraform {
  backend "azurerm" {
    resource_group_name  = ""
    storage_account_name = ""
    container_name       = ""
    key                  = "fabric-e2e-dev.tfstate"
    subscription_id      = ""
  }
}
