# ---------------------------------------------------------------------------
# Prod Environment — Default Variable Values
# ---------------------------------------------------------------------------
# NOTE: subscription_id is not stored here — pass via TF_VAR_subscription_id or -var flag

environment         = "prod"
location            = "eastus"
capacity_sku        = "F8"
resource_group_name = "rg-contoso-fabric-prod"
project_prefix      = "contoso"

admin_members = []

tags = {
  project     = "contoso-fabric-e2e"
  environment = "prod"
  managed_by  = "terraform"
}
