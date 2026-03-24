terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state-prod"
    storage_account_name = "sttfstate7524"
    container_name       = "tfstate"
    key                  = "fabric-e2e-dev.tfstate"
    subscription_id      = "78118340-da1a-4f38-a514-1afe4d4378c0"
  }
}
