# ---------------------------------------------------------------------------
# Dev Environment — Default Variable Values
# ---------------------------------------------------------------------------

environment         = "dev"
location            = "eastus"
capacity_sku        = "F8"
subscription_id     = "78118340-da1a-4f38-a514-1afe4d4378c0"
resource_group_name = "rg-contoso-fabric-dev"

admin_members = []

tags = {
  project     = "contoso-fabric-e2e"
  environment = "dev"
  managed_by  = "terraform"
}
