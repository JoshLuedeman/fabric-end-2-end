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
# Digital Twin Builder (Preview) — placeholder
# ---------------------------------------------------------------------------
# Digital Twin Builder does not yet have a Terraform resource in the
# microsoft/fabric provider (~> 1.8).  Uncomment the blocks below when
# the provider adds support.  Until then, configure twins manually in the
# Fabric portal using the models in src/digital-twins/.
#
# module "store_digital_twin" {
#   source = "../../modules/fabric-digital-twin"
#
#   workspace_id     = module.fabric_workspaces["real-time"].workspace_id
#   display_name     = "${var.project_prefix}_store_twin"
#   description      = "Digital twin of Contoso retail stores — physical layout, equipment, IoT telemetry (${var.environment})"
#   model_definition = "${path.root}/../../../src/digital-twins/store_twin_model.json"
#   eventhouse_id    = module.eventhouse.eventhouse_id
#   kql_database_id  = fabric_kql_database.realtime_db.id
# }
#
# module "supply_chain_digital_twin" {
#   source = "../../modules/fabric-digital-twin"
#
#   workspace_id     = module.fabric_workspaces["real-time"].workspace_id
#   display_name     = "${var.project_prefix}_supply_chain_twin"
#   description      = "Digital twin of Contoso supply chain — suppliers, warehouses, DCs, transport (${var.environment})"
#   model_definition = "${path.root}/../../../src/digital-twins/supply_chain_twin_model.json"
#   eventhouse_id    = module.eventhouse.eventhouse_id
#   kql_database_id  = fabric_kql_database.realtime_db.id
# }

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

# ---------------------------------------------------------------------------
# Fabric Deployment Pipelines (native ALM — Dev → Test → Prod)
# Requires preview = true in fabric provider configuration.
# ---------------------------------------------------------------------------
module "deployment_pipeline_retail" {
  source = "../../modules/fabric-deployment-pipeline"

  display_name = "Retail Data Pipeline"
  description  = "Promotes ingestion & data engineering items (${var.environment})"

  stages = [
    {
      display_name = "Development"
      description  = "Active development — ingestion and data engineering"
      is_public    = false
      workspace_id = module.fabric_workspaces["ingestion"].workspace_id
    },
    {
      display_name = "Test"
      description  = "Integration testing and UAT"
      is_public    = false
    },
    {
      display_name = "Production"
      description  = "Live production environment"
      is_public    = false
    },
  ]
}

module "deployment_pipeline_analytics" {
  source = "../../modules/fabric-deployment-pipeline"

  display_name = "Analytics & Reporting"
  description  = "Promotes warehouse, semantic models, and reports (${var.environment})"

  stages = [
    {
      display_name = "Development"
      description  = "Analytics development workspace"
      is_public    = false
      workspace_id = module.fabric_workspaces["analytics"].workspace_id
    },
    {
      display_name = "Test"
      description  = "Report validation and UAT"
      is_public    = false
    },
    {
      display_name = "Production"
      description  = "Live dashboards and reports"
      is_public    = false
    },
  ]
}

module "deployment_pipeline_realtime" {
  source = "../../modules/fabric-deployment-pipeline"

  display_name = "Real-Time Intelligence"
  description  = "Promotes eventstreams, eventhouse, and Reflex triggers (${var.environment})"

  stages = [
    {
      display_name = "Development"
      description  = "Real-time development workspace"
      is_public    = false
      workspace_id = module.fabric_workspaces["real-time"].workspace_id
    },
    {
      display_name = "Test"
      description  = "Load testing and validation"
      is_public    = false
    },
    {
      display_name = "Production"
      description  = "Live streaming analytics"
      is_public    = false
    },
  ]
}

module "deployment_pipeline_datascience" {
  source = "../../modules/fabric-deployment-pipeline"

  display_name = "AI & Data Science"
  description  = "Promotes ML notebooks, models, and experiments (${var.environment})"

  stages = [
    {
      display_name = "Development"
      description  = "ML experimentation workspace"
      is_public    = false
      workspace_id = module.fabric_workspaces["data-science"].workspace_id
    },
    {
      display_name = "Test"
      description  = "Model validation and champion/challenger testing"
      is_public    = false
    },
    {
      display_name = "Production"
      description  = "Production model serving"
      is_public    = false
    },
  ]
}

# ---------------------------------------------------------------------------
# Fabric ML Models (registered model containers for MLflow)
# Requires preview = true in fabric provider configuration.
# ---------------------------------------------------------------------------
module "ml_model_demand_forecaster" {
  source = "../../modules/fabric-ml-model"

  workspace_id = module.fabric_workspaces["data-science"].workspace_id
  display_name = "demand-forecaster"
  description  = "Prophet-based demand forecasting model for store × category predictions (${var.environment})"
}

module "ml_model_churn_predictor" {
  source = "../../modules/fabric-ml-model"

  workspace_id = module.fabric_workspaces["data-science"].workspace_id
  display_name = "churn-predictor"
  description  = "LightGBM churn prediction model for customer retention (${var.environment})"
}

# ---------------------------------------------------------------------------
# Fabric Domains — logical workspace grouping for governance
# ---------------------------------------------------------------------------
module "fabric_domains" {
  source = "../../modules/fabric-domains"

  workspace_ids = {
    for area in local.workspace_areas : area => module.fabric_workspaces[area].workspace_id
  }
}

# ---------------------------------------------------------------------------
# Variable Library — environment-specific configuration
# ---------------------------------------------------------------------------
module "variable_library" {
  source = "../../modules/fabric-variable-library"

  workspace_id   = module.fabric_workspaces["governance"].workspace_id
  project_prefix = var.project_prefix
  environment    = var.environment
}

# ---------------------------------------------------------------------------
# Dataflows Gen2 — Power Query M transformations in data-engineering workspace
# ---------------------------------------------------------------------------
module "dataflows_gen2" {
  source = "../../modules/fabric-dataflow-gen2"

  workspace_id = module.fabric_workspaces["data-engineering"].workspace_id

  dataflows = {
    customer_cleansing = {
      display_name  = "${var.project_prefix}_df_customer_cleansing"
      description   = "Dedup, standardize addresses, normalize phone numbers (${var.environment})"
      mashup_path   = "${path.module}/../../../src/dataflows/df_customer_cleansing.pq"
      metadata_path = "${path.module}/../../../src/dataflows/df_customer_cleansing_metadata.json"
    }
    product_enrichment = {
      display_name  = "${var.project_prefix}_df_product_enrichment"
      description   = "Enrich product catalog: margin %, category rollup, seasonal flags (${var.environment})"
      mashup_path   = "${path.module}/../../../src/dataflows/df_product_enrichment.pq"
      metadata_path = "${path.module}/../../../src/dataflows/df_product_enrichment_metadata.json"
    }
    incremental_sales_load = {
      display_name  = "${var.project_prefix}_df_incremental_sales_load"
      description   = "Watermark-based incremental load from bronze to silver (${var.environment})"
      mashup_path   = "${path.module}/../../../src/dataflows/df_incremental_sales_load.pq"
      metadata_path = "${path.module}/../../../src/dataflows/df_incremental_sales_load_metadata.json"
    }
  }
}

# ---------------------------------------------------------------------------
# Mirrored Database — ERP replication into OneLake via continuous CDC
# ---------------------------------------------------------------------------
module "erp_mirror" {
  source = "../../modules/fabric-mirroring"

  workspace_id    = module.fabric_workspaces["ingestion"].workspace_id
  display_name    = "${var.project_prefix}_erp_mirror"
  description     = "Continuous CDC mirror of Azure SQL ERP (Suppliers, POs, GL) into OneLake (${var.environment})"
  definition_path = "${path.module}/../../../src/mirroring/mirror_config.json"
}

# ---------------------------------------------------------------------------
# Mirrored Database — Snowflake supply chain partner data into OneLake
# ---------------------------------------------------------------------------
module "snowflake_mirror" {
  source = "../../modules/fabric-mirroring"

  workspace_id    = module.fabric_workspaces["ingestion"].workspace_id
  display_name    = "${var.project_prefix}_snowflake_supply_chain_mirror"
  description     = "Continuous CDC mirror of Snowflake partner supply chain data (${var.environment})"
  definition_path = "${path.module}/../../../src/mirroring/mirror_snowflake_config.json"
}

# ---------------------------------------------------------------------------
# Mirrored Database — Cosmos DB operational data into analytical Lakehouse
# ---------------------------------------------------------------------------
module "cosmos_mirror" {
  source = "../../modules/fabric-mirroring"

  workspace_id    = module.fabric_workspaces["ingestion"].workspace_id
  display_name    = "${var.project_prefix}_cosmos_mirror"
  description     = "Continuous CDC mirror of Cosmos DB (product catalog, customer 360) into OneLake (${var.environment})"
  definition_path = "${path.module}/../../../src/mirroring/mirror_cosmos_config.json"
}

# ---------------------------------------------------------------------------
# Cosmos DB — NoSQL document store for product catalog, customer 360, orders
# NOTE: Placeholder module — Fabric Terraform provider does not yet support
# Cosmos DB natively. See module README for REST API / portal setup steps.
# ---------------------------------------------------------------------------
module "cosmos_db" {
  source = "../../modules/fabric-cosmosdb"

  workspace_id = module.fabric_workspaces["data-warehouse"].workspace_id
  display_name = "${var.project_prefix}_cosmosdb"
  description  = "NoSQL document store: product catalog, customer 360, order events (${var.environment})"

  throughput_mode   = "Serverless"
  consistency_level = "Session"

  containers = [
    {
      name          = "product_catalog"
      partition_key = "/category/l1"
      unique_keys   = ["/product_id"]
    },
    {
      name          = "customer_360"
      partition_key = "/loyalty_tier"
      unique_keys   = ["/customer_id"]
    },
    {
      name          = "order_events"
      partition_key = "/order_id"
      unique_keys   = ["/event_id"]
    },
  ]
}

# ---------------------------------------------------------------------------
# PostgreSQL — Marketing analytics database (open-source compatibility)
# NOTE: Placeholder module — Fabric Terraform provider does not yet support
# PostgreSQL natively. See module README for REST API / portal setup steps.
# ---------------------------------------------------------------------------
module "postgresql_marketing" {
  source = "../../modules/fabric-postgresql"

  workspace_id = module.fabric_workspaces["analytics"].workspace_id
  display_name = "${var.project_prefix}_marketing_analytics_pg"
  description  = "Marketing team PostgreSQL DB: campaigns, attribution, A/B tests, geo-analysis (${var.environment})"

  pg_version = "16"
  extensions = ["postgis", "pg_trgm", "uuid-ossp"]
}

# ---------------------------------------------------------------------------
# OneLake Shortcuts — zero-copy virtual links to external and cross-workspace data
# NOTE: fabric_shortcut is a preview resource. Ensure preview mode is enabled
# in the provider configuration.
# ---------------------------------------------------------------------------
module "shortcuts" {
  source = "../../modules/fabric-shortcuts"

  workspace_id = module.fabric_workspaces["data-engineering"].workspace_id
  lakehouse_id = module.lakehouses["bronze"].lakehouse_id

  adls_gen2_shortcuts = {
    weather_data = {
      name          = "weather_daily_feed"
      path          = "Files/external/weather"
      location      = "https://stweatherdataeastus.dfs.core.windows.net"
      subpath       = "/weather-feed/daily"
      connection_id = var.weather_adls_connection_id
    }
  }

  onelake_shortcuts = {
    gold_to_warehouse = {
      name                = "gold_tables"
      path                = "Tables/gold"
      target_workspace_id = module.fabric_workspaces["data-engineering"].workspace_id
      target_item_id      = module.lakehouses["gold"].lakehouse_id
      target_path         = "Tables"
    }
  }
}

# ---------------------------------------------------------------------------
# GraphQL API — unified API layer for exposing warehouse data to applications
# ---------------------------------------------------------------------------
module "graphql_api" {
  source = "../../modules/fabric-graphql"

  workspace_id     = module.fabric_workspaces["data-warehouse"].workspace_id
  display_name     = "${var.project_prefix}_retail_api"
  description      = "Contoso Retail GraphQL API — unified query layer for products, stores, customers, sales, and inventory (${var.environment})"
  data_source_id   = module.warehouse.warehouse_id
  data_source_type = "warehouse"
  schema_path      = "${path.module}/../../../src/graphql/schema/retail_api.graphql"
}

# ---------------------------------------------------------------------------
# Copy Jobs — bulk and incremental data movement
# ---------------------------------------------------------------------------
module "copy_jobs" {
  source = "../../modules/fabric-copy-job"

  workspace_id = module.fabric_workspaces["ingestion"].workspace_id

  copy_jobs = {
    daily_erp_extract = {
      display_name    = "${var.project_prefix}_cj_daily_erp_extract"
      description     = "Daily bulk copy from ERP mirror to bronze staging (${var.environment})"
      definition_path = "${path.module}/../../../src/copy-jobs/cj_daily_erp_extract.json"
    }
    incremental_crm_sync = {
      display_name    = "${var.project_prefix}_cj_incremental_crm_sync"
      description     = "Hourly incremental CDC sync of CRM data to bronze (${var.environment})"
      definition_path = "${path.module}/../../../src/copy-jobs/cj_incremental_crm_sync.json"
    }
  }
}
