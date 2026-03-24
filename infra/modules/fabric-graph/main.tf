# ---------------------------------------------------------------------------
# Module: fabric-graph
# Creates a Microsoft Fabric GraphQL API resource.
#
# NOTE: The GraphQL API resource (fabric_graphql_api) is available in the
# microsoft/fabric provider. A dedicated "Graph Database" resource type
# announced at FabCon 2026 may require a newer provider version when it
# becomes generally available. For now, this module uses the existing
# fabric_graphql_api resource.
# ---------------------------------------------------------------------------

resource "fabric_graphql_api" "this" {
  display_name = var.display_name
  description  = var.description
  workspace_id = var.workspace_id
}
