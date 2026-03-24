# ---------------------------------------------------------------------------
# Bootstrap — Service Principal & Fabric Admin Setup
#
# This configuration creates an Azure AD application and service principal
# for Terraform automation, and assigns it the necessary permissions for
# managing Microsoft Fabric resources.
#
# Run this once before deploying the dev/prod environments.
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.9"

  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.0"
    }

    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0"
    }
  }
}

provider "azuread" {}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
variable "app_display_name" {
  description = "Display name for the Terraform automation application."
  type        = string
  default     = "sp-fabric-terraform-automation"
}

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

# ---------------------------------------------------------------------------
# Data Sources
# ---------------------------------------------------------------------------
data "azuread_client_config" "current" {}

# ---------------------------------------------------------------------------
# Azure AD Application & Service Principal
# ---------------------------------------------------------------------------
resource "azuread_application" "terraform" {
  display_name = var.app_display_name
  owners       = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "terraform" {
  client_id = azuread_application.terraform.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_password" "terraform" {
  application_id = azuread_application.terraform.id
  display_name   = "terraform-automation"
  end_date       = "2026-12-31T00:00:00Z"
}

# ---------------------------------------------------------------------------
# Role Assignment — Contributor on the subscription
# (Adjust scope as needed for least-privilege)
# ---------------------------------------------------------------------------
resource "azurerm_role_assignment" "contributor" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.terraform.object_id
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "client_id" {
  description = "The Application (Client) ID for the Terraform SPN."
  value       = azuread_application.terraform.client_id
}

output "client_secret" {
  description = "The client secret for the Terraform SPN. Store securely!"
  value       = azuread_application_password.terraform.value
  sensitive   = true
}

output "tenant_id" {
  description = "The Azure AD Tenant ID."
  value       = data.azuread_client_config.current.tenant_id
}

output "service_principal_object_id" {
  description = "The Object ID of the service principal (use for Fabric Capacity admin_members)."
  value       = azuread_service_principal.terraform.object_id
}
