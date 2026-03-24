# ---------------------------------------------------------------------------
# Module: fabric-deployment-pipeline
# Creates a Microsoft Fabric Deployment Pipeline with staged workspace
# promotion (Dev → Test → Production).
#
# NOTE: This resource requires preview mode enabled in the fabric provider
# configuration: preview = true
#
# Fabric Deployment Pipelines are the native ALM (Application Lifecycle
# Management) feature for promoting Fabric items across environments.
# They complement — but do not replace — GitHub Actions CI/CD, which
# handles IaC (Terraform) and notebook source control.
# ---------------------------------------------------------------------------

resource "fabric_deployment_pipeline" "this" {
  display_name = var.display_name
  description  = var.description

  # stages is an Attributes List — assigned directly, not as a nested block.
  # The provider example uses: stages = [ { ... }, { ... } ]
  stages = [
    for stage in var.stages : {
      display_name = stage.display_name
      description  = stage.description
      is_public    = stage.is_public
      workspace_id = stage.workspace_id
    }
  ]
}
