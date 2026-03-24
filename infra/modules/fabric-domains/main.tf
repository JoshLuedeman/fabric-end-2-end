# ---------------------------------------------------------------------------
# Module: fabric-domains
# Creates Fabric Domains for logical workspace grouping and governance.
#
# NOTE: As of microsoft/fabric provider v1.8.0, there is no dedicated
# "fabric_domain" resource. This module uses terraform_data placeholders
# to document the domain configuration intent. When the provider adds
# native domain support, migrate to the real resource.
#
# In the meantime, domains can be managed via the Fabric REST API:
#   POST https://api.fabric.microsoft.com/v1/admin/domains
#   PATCH https://api.fabric.microsoft.com/v1/admin/domains/{domainId}
#   POST https://api.fabric.microsoft.com/v1/admin/domains/{domainId}/assignWorkspaces
#
# Reference: https://learn.microsoft.com/en-us/rest/api/fabric/admin/domains
# ---------------------------------------------------------------------------

locals {
  domain_definitions = {
    "retail-operations" = {
      name           = "Retail Operations"
      description    = "Core retail data platform — ingestion, transformation, and warehousing for POS, inventory, and store operations across 500 stores."
      parent_domain  = null
      admins_group   = var.admins_groups["retail-operations"]
      workspace_keys = ["ingestion", "data-engineering", "data-warehouse"]
    }
    "customer-intelligence" = {
      name           = "Customer Intelligence"
      description    = "Advanced analytics, ML, and BI for customer segmentation, predictive modeling, and executive reporting."
      parent_domain  = null
      admins_group   = var.admins_groups["customer-intelligence"]
      workspace_keys = ["data-science", "analytics"]
    }
    "supply-chain-logistics" = {
      name           = "Supply Chain & Logistics"
      description    = "Real-time streaming analytics for IoT sensors, fleet tracking, warehouse monitoring, and supply chain events."
      parent_domain  = null
      admins_group   = var.admins_groups["supply-chain-logistics"]
      workspace_keys = ["real-time"]
    }
    "corporate-governance" = {
      name           = "Corporate Governance"
      description    = "Data governance, compliance monitoring, AI agent orchestration, and platform administration."
      parent_domain  = null
      admins_group   = var.admins_groups["corporate-governance"]
      workspace_keys = ["governance", "ai-agents"]
    }
  }
}

# ---------------------------------------------------------------------------
# Placeholder: fabric_domain resources
# Replace with the real resource when provider support is available:
#
# resource "fabric_domain" "this" {
#   for_each    = local.domain_definitions
#   display_name = each.value.name
#   description  = each.value.description
#   parent_domain_id = each.value.parent_domain
# }
#
# resource "fabric_domain_workspace_assignment" "this" {
#   for_each  = { for pair in local.workspace_assignments : "${pair.domain}-${pair.workspace}" => pair }
#   domain_id    = fabric_domain.this[each.value.domain].id
#   workspace_id = each.value.workspace_id
# }
# ---------------------------------------------------------------------------

resource "terraform_data" "domain" {
  for_each = local.domain_definitions

  input = {
    domain_key     = each.key
    name           = each.value.name
    description    = each.value.description
    parent_domain  = each.value.parent_domain
    admins_group   = each.value.admins_group
    workspace_keys = each.value.workspace_keys
    workspace_ids  = [for key in each.value.workspace_keys : lookup(var.workspace_ids, key, null)]
    note           = "Placeholder for Fabric Domain. Provision via REST API or replace with fabric_domain resource when available."
  }
}
