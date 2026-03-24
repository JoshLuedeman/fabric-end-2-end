# ---------------------------------------------------------------------------
# Prod Environment — Contoso Global Retail & Supply Chain
# Composes all modules to create the complete Fabric production environment.
# ---------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------------------
# Locals: Workspace definitions and medallion lakehouse tiers
# ---------------------------------------------------------------------------
locals {
  workspace_areas = [
    "ingestion",
    "data-engineering",
    "data-warehouse",
    "real-time",
    "data-science",
    "analytics",
    "governance",
    "ai-agents",
  ]

  workspace_definitions = {
    for area in local.workspace_areas : area => {
      display_name = "contoso-${area}-${var.environment}"
      description  = "Contoso ${replace(title(replace(area, "-", " ")), " ", " ")} workspace (${var.environment})"
    }
  }

  # Medallion architecture lakehouses for the data-engineering workspace
  lakehouse_tiers = ["bronze", "silver", "gold"]
}

# ---------------------------------------------------------------------------
# Fabric Capacity (F8)
# ---------------------------------------------------------------------------
module "fabric_capacity" {
  source = "../../modules/fabric-capacity"

  name                = "contoso-fabric-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku_name            = var.capacity_sku
  admin_members       = length(var.admin_members) > 0 ? var.admin_members : [data.azurerm_client_config.current.object_id]
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# Fabric Workspaces (8 per environment)
# ---------------------------------------------------------------------------
module "fabric_workspaces" {
  source   = "../../modules/fabric-workspace"
  for_each = local.workspace_definitions

  display_name = each.value.display_name
  description  = each.value.description
  capacity_id  = module.fabric_capacity.capacity_id
}

# ---------------------------------------------------------------------------
# Lakehouses: bronze, silver, gold in data-engineering workspace
# ---------------------------------------------------------------------------
module "lakehouses" {
  source   = "../../modules/fabric-lakehouse"
  for_each = toset(local.lakehouse_tiers)

  workspace_id = module.fabric_workspaces["data-engineering"].workspace_id
  display_name = "lh_${each.value}"
  description  = "Contoso ${title(each.value)} lakehouse — medallion architecture (${var.environment})"
}

# ---------------------------------------------------------------------------
# Warehouse in data-warehouse workspace
# ---------------------------------------------------------------------------
module "warehouse" {
  source = "../../modules/fabric-warehouse"

  workspace_id = module.fabric_workspaces["data-warehouse"].workspace_id
  display_name = "${var.project_prefix}_warehouse"
  description  = "Contoso central data warehouse (${var.environment})"
}

# ---------------------------------------------------------------------------
# SQL Database (OLTP operational database) in data-warehouse workspace
# ---------------------------------------------------------------------------
module "sql_database" {
  source = "../../modules/fabric-sql-database"

  display_name = "${var.project_prefix}_operational_db"
  description  = "OLTP operational database for POS, inventory, and CRM (${var.environment})"
  workspace_id = module.fabric_workspaces["data-warehouse"].workspace_id
}

# ---------------------------------------------------------------------------
# Eventhouse + KQL Database in real-time workspace
# ---------------------------------------------------------------------------
module "eventhouse" {
  source = "../../modules/fabric-eventhouse"

  workspace_id = module.fabric_workspaces["real-time"].workspace_id
  display_name = "${var.project_prefix}_eventhouse"
  description  = "Contoso real-time analytics eventhouse (${var.environment})"
}

resource "fabric_kql_database" "realtime_db" {
  display_name = "${var.project_prefix}_kqldb"
  description  = "Contoso real-time KQL database (${var.environment})"
  workspace_id = module.fabric_workspaces["real-time"].workspace_id

  configuration = {
    database_type = "ReadWrite"
    eventhouse_id = module.eventhouse.eventhouse_id
  }
}

# ---------------------------------------------------------------------------
# Azure Storage Account for staging source data
# ---------------------------------------------------------------------------
module "staging_storage" {
  source = "../../modules/azure-storage"

  name                = "stcontosostaging${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  container_names     = ["raw-data", "reference-data", "staging"]
  tags                = var.tags
}
