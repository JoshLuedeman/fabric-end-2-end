# ---------------------------------------------------------------------------
# Dev Environment — Default Variable Values
# ---------------------------------------------------------------------------
# NOTE: subscription_id is not stored here — pass via TF_VAR_subscription_id or -var flag

environment         = "dev"
location            = "eastus"
resource_group_name = "rg-contoso-fabric-dev"
project_prefix      = "contoso"

admin_members = []

tags = {
  project     = "contoso-fabric-e2e"
  environment = "dev"
  managed_by  = "terraform"
}
