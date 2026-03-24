variable "name" {
  description = "The name of the Fabric Capacity. Must be globally unique."
  type        = string
}

variable "resource_group_name" {
  description = "The name of the resource group in which to create the Fabric Capacity."
  type        = string
}

variable "location" {
  description = "The Azure region for the Fabric Capacity."
  type        = string
}

variable "sku_name" {
  description = "The SKU name for the Fabric Capacity."
  type        = string
  default     = "F8"

  validation {
    condition     = contains(["F2", "F4", "F8", "F16", "F32", "F64", "F128", "F256", "F512", "F1024", "F2048"], var.sku_name)
    error_message = "sku_name must be a valid Fabric capacity SKU: F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, or F2048."
  }
}

variable "admin_members" {
  description = "List of admin user UPNs or service principal object IDs for the capacity."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to the Fabric Capacity."
  type        = map(string)
  default     = {}
}
