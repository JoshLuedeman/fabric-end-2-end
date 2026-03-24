variable "display_name" {
  description = "The display name of the Fabric Connection (max 123 characters)."
  type        = string
}

variable "connectivity_type" {
  description = "The connectivity type. Valid values: ShareableCloud, VirtualNetworkGateway."
  type        = string
  default     = "ShareableCloud"
}

variable "connection_details" {
  description = "Connection details including type, creation_method, and optional parameters."
  type = object({
    type            = string
    creation_method = string
    parameters = optional(list(object({
      name  = string
      value = string
    })), [])
  })
}

variable "credential_type" {
  description = "The credential type. Valid values: Anonymous, Basic, Key, ServicePrincipal, WorkspaceIdentity, etc."
  type        = string
  default     = "Anonymous"
}

variable "connection_encryption" {
  description = "The connection encryption type. Valid values: Any, Encrypted, NotEncrypted."
  type        = string
  default     = "NotEncrypted"
}

variable "privacy_level" {
  description = "The privacy level. Valid values: None, Organizational, Private, Public."
  type        = string
  default     = "Organizational"
}

variable "skip_test_connection" {
  description = "Whether to skip the test connection during creation."
  type        = bool
  default     = false
}
