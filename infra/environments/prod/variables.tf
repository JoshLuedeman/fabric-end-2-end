variable "environment" {
  description = "The deployment environment name."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "The Azure region for all resources."
  type        = string
  default     = "eastus"
}

variable "capacity_sku" {
  description = "The Fabric Capacity SKU (e.g. F2, F4, F8, F16, F32)."
  type        = string
  default     = "F8"
}

variable "subscription_id" {
  description = "The Azure subscription ID."
  type        = string
}

variable "resource_group_name" {
  description = "The resource group name for Azure resources."
  type        = string
}

variable "admin_members" {
  description = "List of admin user UPNs or service principal object IDs for the Fabric Capacity."
  type        = list(string)
  default     = []
}

variable "project_prefix" {
  description = "Prefix for Fabric resource display names"
  type        = string
  default     = "contoso"
}

variable "tags" {
  description = "Tags to apply to all resources."
  type        = map(string)
  default = {
    project     = "contoso-fabric-e2e"
    environment = "prod"
    managed_by  = "terraform"
  }
}
