terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0"
    }

    fabric = {
      source  = "microsoft/fabric"
      version = ">= 1.8.0"
    }

    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "fabric" {
  # Authentication is handled via environment variables or Azure CLI.
  # Set ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_TENANT_ID for SPN auth.
}

provider "azuread" {}
