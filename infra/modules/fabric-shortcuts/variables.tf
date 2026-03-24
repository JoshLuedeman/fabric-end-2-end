variable "workspace_id" {
  description = "The ID of the Fabric Workspace containing the Lakehouse where shortcuts will be created."
  type        = string
}

variable "lakehouse_id" {
  description = "The ID of the Lakehouse item where shortcuts will be mounted."
  type        = string
}

variable "adls_gen2_shortcuts" {
  description = <<-EOT
    Map of ADLS Gen2 shortcuts to create. Each entry defines a virtual link to
    data in an Azure Data Lake Storage Gen2 account (no data copy).
  EOT
  type = map(object({
    name          = string
    path          = string # e.g. "Files/external/weather"
    location      = string # e.g. "https://stweatherdata.dfs.core.windows.net"
    subpath       = string # e.g. "/weather-feed/daily"
    connection_id = string
  }))
  default = {}
}

variable "onelake_shortcuts" {
  description = <<-EOT
    Map of OneLake cross-workspace shortcuts. Each entry creates a virtual link
    to tables or files in another workspace's Lakehouse, Warehouse, or KQL DB.
  EOT
  type = map(object({
    name                = string
    path                = string # e.g. "Tables/gold"
    target_workspace_id = string
    target_item_id      = string
    target_path         = string # e.g. "Tables"
  }))
  default = {}
}

# variable "s3_shortcuts" {
#   description = <<-EOT
#     Map of Amazon S3 shortcuts. Each entry creates a virtual link to data in
#     an S3 bucket (e.g., partner product catalog, third-party market data).
#   EOT
#   type = map(object({
#     name          = string
#     path          = string
#     location      = string # e.g. "https://partner-bucket.s3.us-east-1.amazonaws.com"
#     subpath       = string
#     connection_id = string
#   }))
#   default = {}
# }
