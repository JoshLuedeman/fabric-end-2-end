# Demo Guide

Step-by-step guide for running the Contoso Global Retail & Supply Chain demo.

## Prerequisites

1. Azure subscription with Fabric F8 capacity provisioned
2. Service principal configured (see `infra/bootstrap/README.md`)
3. GitHub repository secrets configured for OIDC auth
4. Tools installed: Terraform, Python 3.12+, Node.js 22+, Fabric CLI

## Demo Flow

### Act 1: The Data Foundation

**Story**: "Contoso is a global retailer operating 150 stores across 5 countries. They need a unified data platform to drive insights across sales, supply chain, and operations."

#### 1.1 Show the Infrastructure (Terraform)
- Open `infra/environments/dev/main.tf` — show the declarative workspace layout
- Show 8 workspaces organized by workload (ingestion, engineering, warehouse, real-time, etc.)
- Highlight the composable module pattern for Backstage integration

#### 1.2 Explore OneLake
- Navigate to OneLake in the Fabric portal
- Show the unified storage across all workloads
- Demonstrate OneLake Catalog search (FabCon 2026 GA)

#### 1.3 Data Ingestion
- Show the bronze Lakehouse with raw Parquet files
- Walk through `ingest_sales.py` notebook — raw data → Delta table
- Execute a Data Factory pipeline (`pl_ingest_daily`) to orchestrate ingestion

### Act 2: Data Engineering

**Story**: "Raw data needs cleansing and transformation to be business-ready."

#### 2.1 Medallion Architecture
- Bronze: Raw ingestion with metadata columns
- Silver: `transform_sales.py` — data quality, deduplication, derived columns
- Gold: `fact_sales.py` — star schema fact table with surrogate keys

#### 2.2 Data Warehouse
- Show the warehouse star schema (dims + facts)
- Run `vw_sales_summary` — aggregated view for reporting
- Demonstrate cross-database queries between Lakehouse and Warehouse

### Act 3: Real-Time Intelligence

**Story**: "Contoso needs to monitor operations in real-time — POS transactions, IoT sensors, inventory levels."

#### 3.1 Start the Event Generator
```bash
make stream-run
```
- Show events flowing in the console (POS, IoT, inventory)

#### 3.2 Eventstream & Eventhouse
- Open the Eventstream in Fabric — show events routing to KQL DB
- Run `sales_anomaly_detection.kql` — detect unusual sales patterns
- Run `iot_device_health.kql` — identify sensors reporting anomalies
- Show the real-time operations dashboard

### Act 4: Analytics & Business Intelligence

**Story**: "Executives and operations managers need actionable insights."

#### 4.1 Power BI Reports
- **Executive Dashboard**: Revenue trends, regional performance, KPIs
- **Sales Analytics**: Product-level analysis, customer segmentation
- **Inventory Operations**: Stock levels, reorder alerts, supply chain health
- **Real-Time Monitoring**: Live event streams, anomaly alerts

#### 4.2 OneLake Security
- Demonstrate row-level security — different users see different regions
- Show column-level security — PII hidden from analysts

#### 4.3 Copilot
- Ask Copilot natural language questions about sales performance
- Generate a new visual using Copilot

### Act 5: FabCon/SQLCon 2026 Features

**Story**: "The latest innovations transform Fabric from a data platform into an enterprise intelligence layer."

#### 5.1 Graph in Fabric
- Open the supply chain graph model
- Run GQL query: "Find the shortest supply path from Supplier SUP-042 to Store S-015"
- Visualize supplier-warehouse-store relationships
- Show how graph enriches AI agent context

#### 5.2 Data Agents (GA)
- Open the **Sales Analyst** agent
- Ask: "What were total sales last quarter by region?"
- Ask: "Why did sales drop in the South region last week?"
- Open the **Supply Chain Advisor** agent
- Ask: "Which suppliers have delivery issues?"
- Ask: "Which products are at risk of stockout?"

#### 5.3 Translytical Task Flows
- Open the Sales Analytics report
- Click "Qualify Lead" on a customer row — fill in status, notes, follow-up date
- Show the write-back record in the warehouse
- Open the Inventory Operations report
- Click "Reorder Stock" on a below-reorder product — adjust quantity, set priority
- Show the reorder request created via User Data Function

#### 5.4 Fabric IQ + Ontology
- Show how Fabric IQ infers business context from data
- Demonstrate contextual intelligence powering the data agents

#### 5.5 Database Hub
- Open Database Hub — show unified view across all databases
- SQL Server, Fabric Warehouse, KQL databases in one place

#### 5.6 Branched Workspaces
- Create a feature branch workspace
- Make changes in the branch
- Show diff and merge workflow

### Act 6: DevOps & Automation

**Story**: "Everything you've seen is fully automated and reproducible."

#### 6.1 GitHub Actions
- Show the 5 workflow files
- Trigger `deploy-infra.yml` — Terraform plan with approval gate
- Show `deploy-content.yml` — Fabric CLI deploying notebooks and reports

#### 6.2 Reproducibility
- Run `make deploy-all ENVIRONMENT=dev` — full environment in one command
- Show `make tf-destroy ENVIRONMENT=dev` — clean teardown

## Tips for Presenters

- Start the event generator 5 minutes before the real-time demo
- Use the executive dashboard for business audiences, warehouse SQL for technical audiences
- The translytical task flows are the "wow moment" — save them for the middle
- Keep the graph demo visual — the supply chain relationships are impressive on screen
- The Data Agents work best with specific questions, not vague ones
