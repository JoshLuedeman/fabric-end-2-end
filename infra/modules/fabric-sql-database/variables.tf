variable "display_name" {
  description = "Display name for the SQL Database"
  type        = string
}

variable "description" {
  description = "Description for the SQL Database"
  type        = string
  default     = ""
}

variable "workspace_id" {
  description = "Fabric workspace ID"
  type        = string
}

# ---------------------------------------------------------------------------
# Change Event Streaming (used by the commented-out null_resource above)
# ---------------------------------------------------------------------------

variable "eventstream_id" {
  description = "Fabric Eventstream ID to receive CDC change events. Required when enabling Change Event Streaming."
  type        = string
  default     = ""
}

variable "change_event_tables" {
  description = "List of table names to monitor for Change Event Streaming."
  type        = list(string)
  default     = ["Transactions", "TransactionItems", "Inventory", "CustomerInteractions"]
}
