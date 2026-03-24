variable "workspace_id" {
  description = "The ID of the Fabric Workspace where the Cosmos DB will be created."
  type        = string
}

variable "display_name" {
  description = "Display name for the Cosmos DB database."
  type        = string
}

variable "description" {
  description = "Description for the Cosmos DB database."
  type        = string
  default     = ""
}

variable "throughput_mode" {
  description = "Throughput provisioning mode: 'Provisioned' or 'Serverless'."
  type        = string
  default     = "Serverless"

  validation {
    condition     = contains(["Provisioned", "Serverless"], var.throughput_mode)
    error_message = "throughput_mode must be 'Provisioned' or 'Serverless'."
  }
}

variable "consistency_level" {
  description = "Default consistency level for the Cosmos DB account."
  type        = string
  default     = "Session"

  validation {
    condition     = contains(["Strong", "BoundedStaleness", "Session", "ConsistentPrefix", "Eventual"], var.consistency_level)
    error_message = "consistency_level must be one of: Strong, BoundedStaleness, Session, ConsistentPrefix, Eventual."
  }
}

variable "containers" {
  description = "Map of Cosmos DB containers to create, each with partition_key and optional unique_keys."
  type = list(object({
    name          = string
    partition_key = string
    unique_keys   = optional(list(string), [])
  }))
  default = [
    {
      name          = "product_catalog"
      partition_key = "/category/l1"
      unique_keys   = ["/product_id"]
    },
    {
      name          = "customer_360"
      partition_key = "/loyalty_tier"
      unique_keys   = ["/customer_id"]
    },
    {
      name          = "order_events"
      partition_key = "/order_id"
      unique_keys   = ["/event_id"]
    }
  ]
}
