# ---------------------------------------------------------------------------
# Module: fabric-graphql
# Creates a Microsoft Fabric GraphQL API for exposing warehouse/lakehouse data
# through a unified API layer.
#
# The fabric_graphql_api resource is available in the microsoft/fabric provider
# (>= 1.0). This module creates the API item in Fabric; data-source binding
# and schema deployment are performed post-provisioning via the Fabric portal
# or the Fabric REST API (see src/graphql/docs/graphql_setup.md).
#
# After terraform apply:
#   1. Open the GraphQL API in the Fabric portal
#   2. Connect it to the target warehouse / lakehouse data source
#   3. Import or author the schema (see src/graphql/schema/)
#   4. Configure authentication and CORS (see src/graphql/config/)
# ---------------------------------------------------------------------------

resource "fabric_graphql_api" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id

  # NOTE: The fabric_graphql_api resource creates the API item container.
  # Data-source binding (warehouse_id / lakehouse_id) and schema definition
  # are configured post-provisioning because the Terraform provider does not
  # yet expose these as inline attributes. Use the Fabric REST API:
  #   POST https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/graphqlApis/{api_id}/datasources
  # or the portal wizard to complete the setup.
}
