# ---------------------------------------------------------------------------
# Module: fabric-ml-model
# Creates a Microsoft Fabric ML Model resource.
#
# NOTE: This resource requires preview mode enabled in the fabric provider
# configuration: preview = true
#
# NOTE: This resource does NOT support Service Principal authentication.
# You must use User context authentication (Azure CLI / interactive).
#
# The ML Model resource registers a model container in the Fabric workspace.
# Model versions are managed by MLflow inside notebooks — this Terraform
# resource creates the top-level model entry that notebooks populate via
# mlflow.register_model().
# ---------------------------------------------------------------------------

resource "fabric_ml_model" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}
