# Database Mirroring Setup Guide — Contoso Global Retail

> **Fabric Mirroring** replicates external databases into OneLake with near-real-time
> CDC (Change Data Capture). Data lands in Delta-Parquet format and is immediately
> queryable via the Lakehouse SQL endpoint, notebooks, and semantic models.

## Table of Contents

1. [Overview](#overview)
2. [Mirror Types in This Demo](#mirror-types-in-this-demo)
3. [Setup: Azure SQL Mirror (ERP)](#setup-azure-sql-mirror-erp)
4. [Setup: Snowflake Mirror (Supply Chain Partners)](#setup-snowflake-mirror-supply-chain-partners)
5. [Setup: Cosmos DB Mirror (Operational NoSQL)](#setup-cosmos-db-mirror-operational-nosql)
6. [CDC Behavior & Latency](#cdc-behavior--latency)
7. [Decision Matrix: Mirroring vs Shortcuts vs Copy Job](#decision-matrix-mirroring-vs-shortcuts-vs-copy-job)
8. [Monitoring Mirror Health](#monitoring-mirror-health)
9. [Terraform & REST API Automation](#terraform--rest-api-automation)

---

## Overview

Fabric Mirroring brings data from external sources into OneLake **without building
ETL pipelines**. It uses CDC (Change Data Capture) to stream changes continuously,
so the Lakehouse always has a near-real-time replica.

**Architecture in this demo:**

```
┌─────────────────────┐     CDC     ┌──────────────────────┐     Medallion    ┌─────────────┐
│  Azure SQL (ERP)    │────────────▶│                      │───────────────▶  │  Silver/Gold │
├─────────────────────┤             │   OneLake Bronze     │                  │  Lakehouses  │
│  Snowflake (Supply) │────────────▶│   (Delta-Parquet)    │───────────────▶  │              │
├─────────────────────┤             │                      │                  │  Warehouse   │
│  Cosmos DB (NoSQL)  │────────────▶│                      │───────────────▶  │  SQL Endpt   │
└─────────────────────┘             └──────────────────────┘                  └─────────────┘
```

---

## Mirror Types in This Demo

| Source | Config File | Tables | Use Case |
|--------|-------------|--------|----------|
| **Azure SQL** (ERP) | `mirror_config.json` | Suppliers, PurchaseOrders, PurchaseOrderLines, GLJournalEntries, ChartOfAccounts | Internal ERP data for financial & supply chain analytics |
| **Snowflake** (Partners) | `mirror_snowflake_config.json` | supplier_performance_metrics, raw_material_prices, global_shipping_rates, weather_impact_data | Partner-shared supply chain analytics |
| **Cosmos DB** (NoSQL) | `mirror_cosmos_config.json` | product_catalog, customer_profiles | Operational NoSQL → analytical Lakehouse |

---

## Setup: Azure SQL Mirror (ERP)

This mirror is **managed by Terraform** via the `fabric-mirroring` module.

### Prerequisites
1. Azure SQL Database with CDC enabled on source tables
2. Fabric Connection configured with SQL authentication or Entra ID
3. Network connectivity (private endpoint or public access)

### Steps (Portal — Manual)
1. Navigate to the **ingestion** workspace
2. Click **+ New** → **Mirrored Database**
3. Select **Azure SQL Database** as the source
4. Provide the connection string (or select an existing Fabric Connection)
5. Select tables: `Suppliers`, `PurchaseOrders`, `PurchaseOrderLines`, `GLJournalEntries`, `ChartOfAccounts`
6. Configure replication mode: **Continuous**
7. Click **Create and Start Mirroring**

### Steps (Terraform)
The mirror is already wired in `infra/environments/dev/main.tf`:
```hcl
module "erp_mirror" {
  source          = "../../modules/fabric-mirroring"
  workspace_id    = module.fabric_workspaces["ingestion"].workspace_id
  display_name    = "${var.project_prefix}_erp_mirror"
  definition_path = "${path.module}/../../../src/mirroring/mirror_config.json"
}
```

---

## Setup: Snowflake Mirror (Supply Chain Partners)

### Prerequisites
1. Snowflake account with `CONTOSO_READER` role granted on the shared database
2. Key-pair authentication configured (RSA private key)
3. Fabric Connection for Snowflake created in the workspace

### Steps (Portal)
1. Navigate to the **ingestion** workspace
2. Click **+ New** → **Mirrored Database**
3. Select **Snowflake** as the source
4. Configure connection:
   - **Account**: `<partner-account>.snowflakecomputing.com`
   - **Warehouse**: `CONTOSO_PARTNER_WH`
   - **Database**: `SUPPLY_CHAIN_ANALYTICS`
   - **Authentication**: Key Pair (upload private key via Fabric Connection)
5. Select tables from the `SHARED` schema
6. Set replication mode: **Continuous**
7. Click **Create and Start Mirroring**

### Steps (REST API)
```bash
az rest --method POST \
  --url "https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items" \
  --headers "Content-Type=application/json" \
  --body @src/mirroring/mirror_snowflake_config.json
```

> **Note:** As of mid-2025, Snowflake mirroring requires Fabric Connection
> configuration in the portal first. The REST API can then reference the
> connection ID. See `mirror_snowflake_config.json` for the schema.

---

## Setup: Cosmos DB Mirror (Operational NoSQL)

### Prerequisites
1. Fabric Cosmos DB (or external Azure Cosmos DB) with continuous backup enabled
2. Managed Identity access configured for the Fabric workspace
3. Cosmos DB change feed enabled (on by default)

### Steps (Portal)
1. Navigate to the **ingestion** workspace
2. Click **+ New** → **Mirrored Database**
3. Select **Azure Cosmos DB** as the source
4. Authenticate via **Managed Identity** (recommended) or account key
5. Select database: `contoso_cosmosdb`
6. Select containers: `product_catalog`, `customer_360`
7. Configure column mapping:
   - Flatten depth: 1 (top-level properties become columns)
   - Arrays preserved as JSON strings
8. Set replication mode: **Continuous**
9. Click **Create and Start Mirroring**

### Why not mirror `order_events`?
The `order_events` container has high write volume and benefits from the finer
control of the Spark notebook (`sync_cosmos_to_lakehouse.py`), which handles
dedup, checkpointing, and incremental append logic.

---

## CDC Behavior & Latency

| Source Type | CDC Mechanism | Typical Latency | Notes |
|-------------|--------------|-----------------|-------|
| **Azure SQL** | SQL Server CDC (ct tables) | 5–15 minutes | Depends on source CDC polling interval |
| **Snowflake** | Snowflake Streams + Tasks | 15–30 minutes | Latency depends on Snowflake task schedule |
| **Cosmos DB** | Change Feed | 2–5 minutes | Cosmos DB change feed is near-real-time |
| **PostgreSQL** | Logical Replication | 5–10 minutes | Uses PostgreSQL logical decoding |

### Key behaviors:
- **Initial sync**: Full snapshot on first run (can take hours for large tables)
- **Incremental sync**: Only changed rows after initial sync
- **Schema changes**: DDL changes (new columns) are detected automatically; column removals require mirror restart
- **Deletes**: Soft deletes are captured; hard deletes depend on source CDC support
- **Data format**: All mirrored data lands as Delta-Parquet in OneLake
- **Queryable**: Mirrored tables are immediately queryable via Lakehouse SQL endpoint

---

## Decision Matrix: Mirroring vs Shortcuts vs Copy Job

| Criteria | Mirroring | Shortcuts | Copy Job |
|----------|-----------|-----------|----------|
| **Data movement** | Yes — CDC replication | No — virtual pointer | Yes — batch copy |
| **Freshness** | Near-real-time (minutes) | Real-time (source query) | Scheduled (hourly/daily) |
| **Source types** | Azure SQL, Cosmos DB, Snowflake, PostgreSQL, MySQL | ADLS Gen2, OneLake, S3, GCS | Any JDBC/ODBC source |
| **Data in OneLake** | ✅ Yes (Delta-Parquet) | ❌ No (reads from source) | ✅ Yes (Delta-Parquet) |
| **Query performance** | Fast (local Delta) | Varies (depends on source) | Fast (local Delta) |
| **Cost** | Continuous compute | Minimal (no compute) | Scheduled compute |
| **Schema evolution** | Auto-detected | N/A (source schema) | Manual |
| **Best for** | External DB → Lakehouse | Cross-workspace references, external file shares | Bulk initial loads, historical backfills |

### When to use each:

- **Mirroring** → Your primary choice for replicating operational databases into the analytical Lakehouse. Use when you need near-real-time freshness and the source is a supported database.

- **Shortcuts** → Use for zero-copy access to data that's already in cloud storage (ADLS, S3) or another OneLake workspace. No data movement = no cost. Best for reference data, large file datasets, and cross-workspace sharing.

- **Copy Job** → Use for initial bulk loads, one-time historical backfills, or sources not supported by Mirroring. Also useful for sources behind firewalls where continuous CDC isn't feasible.

### Contoso example:
| Data Source | Method | Rationale |
|-------------|--------|-----------|
| ERP (Azure SQL) | **Mirroring** | Near-real-time financial data for daily reporting |
| Snowflake partners | **Mirroring** | Continuous supplier metrics from partner data share |
| Cosmos DB catalog | **Mirroring** | Product and customer data for analytical joins |
| Weather data (ADLS) | **Shortcut** | External file feed — no need to copy |
| Gold → Warehouse | **Shortcut** | Cross-workspace reference — zero copy |
| Historical CRM archive | **Copy Job** | One-time 5-year backfill |

---

## Monitoring Mirror Health

### Fabric Portal
1. Open the mirrored database in the workspace
2. Click the **Monitor** tab to see:
   - Replication status (Running, Paused, Failed)
   - Last sync timestamp per table
   - Rows replicated (cumulative and delta)
   - Lag (time since last change was captured)

### KQL Queries (Eventhouse)
If you route mirror telemetry to the Eventhouse, query with KQL:

```kql
MirrorTelemetry
| where TimeGenerated > ago(24h)
| summarize
    LastSync = max(TimeGenerated),
    RowsReplicated = sum(RowCount),
    AvgLatencySeconds = avg(LatencySeconds)
  by MirrorName, TableName
| order by LastSync desc
```

### Alerts
Set up Fabric alerts for:
- Mirror stopped/failed → immediate notification
- Replication lag > 30 minutes → warning
- Schema change detected → informational

### REST API Health Check
```bash
# Get mirror status
az rest --method GET \
  --url "https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/mirroredDatabases/{mirror_id}/getStatus"
```

Response includes:
```json
{
  "status": "Running",
  "tables": [
    {
      "tableName": "Suppliers",
      "status": "Replicating",
      "lastSyncTimestamp": "2025-06-01T12:34:56Z",
      "rowsReplicated": 1247,
      "lagSeconds": 45
    }
  ]
}
```

---

## Terraform & REST API Automation

### Managed by Terraform
The `fabric_mirrored_database` resource (microsoft/fabric >= 1.8) supports:
- Azure SQL Database mirrors
- Cosmos DB mirrors (via connection configuration)
- Snowflake mirrors (via connection configuration)

All mirrors use a JSON definition file (`mirroring.json`) passed via the
`definition` block.

### Module usage
```hcl
module "my_mirror" {
  source = "../../modules/fabric-mirroring"

  workspace_id    = module.fabric_workspaces["ingestion"].workspace_id
  display_name    = "${var.project_prefix}_my_mirror"
  description     = "Mirror description"
  definition_path = "${path.module}/../../../src/mirroring/my_mirror_config.json"
}
```

### REST API (for unsupported scenarios)
For operations not yet in Terraform (e.g., pause/resume, monitoring):
```bash
# Pause mirroring
az rest --method POST \
  --url "https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/mirroredDatabases/{mirror_id}/stop"

# Resume mirroring
az rest --method POST \
  --url "https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/mirroredDatabases/{mirror_id}/start"
```
