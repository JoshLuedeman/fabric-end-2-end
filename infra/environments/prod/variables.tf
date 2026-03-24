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
  description = "The Fabric Capacity SKU that controls capacity size AND data generation scale."
  type        = string
  default     = "F8"

  validation {
    condition     = contains(["F2", "F4", "F8", "F16", "F32", "F64", "F128", "F256", "F512", "F1024", "F2048"], var.capacity_sku)
    error_message = "capacity_sku must be a valid Fabric SKU: F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, or F2048."
  }
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
  default     = "tt"
}

variable "tags" {
  description = "Tags to apply to all resources."
  type        = map(string)
  default = {
    project     = "tt-fabric-e2e"
    environment = "prod"
    managed_by  = "terraform"
  }
}

variable "weather_adls_connection_id" {
  description = "Fabric connection ID for the external ADLS Gen2 weather data feed. Required for OneLake shortcuts."
  type        = string
  default     = ""
}
