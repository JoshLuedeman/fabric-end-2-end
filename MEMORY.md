# Project Memory

This file captures project learnings that persist across agent sessions.

## Project Overview

- **Name**: Fabric End-to-End Demo Environment
- **Scenario**: Contoso Global Retail & Supply Chain
- **Fabric Capacity**: Configurable via `FABRIC_SKU` (F2–F64, default F8)
- **Environments**: Dev + Prod (per-workload workspaces × lifecycle stages)

## Tech Stack

- **Infrastructure**: Terraform (microsoft/fabric v1.8.0+, hashicorp/azurerm, hashicorp/azuread)
- **Operational Database**: Fabric SQL Database (OLTP POS system, normalized 3NF, CDC extraction)
- **Data Engineering**: PySpark notebooks (medallion: bronze → silver → gold)
- **Data Integration**: Metadata-driven pipelines (config-table-driven dynamic ingestion)
- **Orchestration**: Apache Airflow (3 DAGs: daily ETL, hourly quality, weekly maintenance)
- **Data Warehouse**: Fabric Warehouse (T-SQL, star schema)
- **Real-Time**: Eventhouse + KQL + Eventstream
- **Analytics**: Power BI (PBIP format, semantic models, translytical task flows)
- **Data Science**: MLflow experiments (demand forecasting, customer segmentation, churn prediction, promotion effectiveness, anomaly detection)
- **Alerting**: Data Activator / Reflex (inventory, sales anomaly, IoT failure, churn risk, promotion performance)
- **Graph**: Fabric Graph (GQL)
- **AI**: Data Agents (sales analyst, supply chain advisor)
- **Streaming**: Node.js/TypeScript event generator
- **Data Generation**: Python (Faker + Pandas) — 14 datasets, 3 new generators (clickstream, interactions, promotions)
- **CI/CD**: GitHub Actions with OIDC auth

## Azure Resources

- **TF State Backend**: sttfstate7524 / tfstate / rg-terraform-state-prod / sub 78118340-da1a-4f38-a514-1afe4d4378c0
- **State Keys**: fabric-e2e-dev.tfstate, fabric-e2e-prod.tfstate

## Design Decisions

- Terraform modules are 1:1 with resource types for future Backstage composability
- All demo data is code-generated (never stored in repo)
- Fabric-native resources preferred over external Azure services
- FabCon/SQLCon 2026 preview features isolated in Phase 6 (toggleable)
- Power BI uses PBIP format for source control
- Fabric SQL Database chosen for OLTP to stay Fabric-native; CDC feeds the lakehouse
- Data Activator / Reflex for automated alerting — keeps the alert loop inside Fabric
- Apache Airflow for orchestration — DAG-based scheduling with dependency management
- Data science notebooks use MLflow for experiment tracking and model versioning
- Metadata-driven pipeline pattern — config table controls ingestion, not code duplication
- Scale target: 532M+ rows, ~40GB across 14 synthetic datasets
- 3 new data generators added: clickstream (150M), customer interactions (10M), promotions + results (20M)

## Active Context

- Initial implementation in progress
- Phases 0-7 defined in plan
