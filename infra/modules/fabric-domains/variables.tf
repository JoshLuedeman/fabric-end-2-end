variable "workspace_ids" {
  description = "Map of workspace area keys to their Fabric Workspace IDs (e.g., { ingestion = 'abc-123', ... })."
  type        = map(string)
}

variable "admins_groups" {
  description = "Map of domain keys to their admin security group names or object IDs."
  type        = map(string)
  default = {
    "retail-operations"      = "sg-fabric-retail-ops-admins"
    "customer-intelligence"  = "sg-fabric-customer-intel-admins"
    "supply-chain-logistics" = "sg-fabric-supply-chain-admins"
    "corporate-governance"   = "sg-fabric-governance-admins"
  }
}
