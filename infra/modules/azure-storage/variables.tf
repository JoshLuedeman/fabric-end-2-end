variable "name" {
  description = "The name of the storage account. Must be globally unique, 3-24 lowercase alphanumeric characters."
  type        = string
}

variable "resource_group_name" {
  description = "The name of the resource group in which to create the storage account."
  type        = string
}

variable "location" {
  description = "The Azure region for the storage account."
  type        = string
}

variable "container_names" {
  description = "List of blob container names to create in the storage account."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to the storage account."
  type        = map(string)
  default     = {}
}
