# Feature Coverage Matrix

This document tracks which Microsoft Fabric features are demonstrated in this environment.

## Legend
- ✅ Implemented and automated
- 🔧 Implemented, manual steps required
- 📋 Planned, not yet implemented
- ⚠️ Preview feature (FabCon/SQLCon 2026)

## Core Platform Features (GA)

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| OneLake | ✅ | Unified storage for all workloads | Terraform |
| Workspaces | ✅ | 8 workspaces per environment | Terraform |
| Fabric Capacity (F2–F64) | ✅ | Provisioned via IaC | Terraform (`FABRIC_SKU`) |
| Git Integration | ✅ | Source-controlled artifacts | GitHub |

## Data Engineering

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Lakehouse | ✅ | Bronze/Silver/Gold medallion | Terraform + Fabric CLI |
| Notebooks (PySpark) | ✅ | 10+ transformation notebooks | Fabric CLI |
| Spark Autoscale | ✅ | Dynamic compute scaling | Terraform config |
| Apache Airflow Jobs | ✅ | 3 DAGs: daily ETL, hourly quality, weekly maintenance | Terraform |

## Data Integration

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Data Factory Pipelines | ✅ | 3 orchestration pipelines | Terraform + Fabric CLI |
| Connections | ✅ | Storage, SQL connections | Terraform |
| CDC from OLTP | ✅ | Fabric SQL Database → Lakehouse via CDC | Notebooks + Pipelines |
| Metadata-Driven Pipelines | ✅ | Config-table-driven dynamic ingestion | Pipelines + Notebooks |
| Database Mirroring | 📋 | SQL/Cosmos mirroring | Terraform |
| SharePoint List Mirroring | ⚠️ | Operational data sync | Manual |

## Data Warehousing

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Warehouse | ✅ | Star schema (dims + facts) | Terraform |
| SQL Endpoint | ✅ | T-SQL access to Lakehouse | Auto-created |
| Stored Procedures | ✅ | Dimension/fact loading | SQL scripts |
| Views | ✅ | Reporting views | SQL scripts |

## Real-Time Intelligence

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Eventhouse | ✅ | Real-time analytics store | Terraform |
| KQL Database | ✅ | Streaming data tables | Terraform |
| Eventstream | ✅ | Event routing | Terraform |
| KQL Queries | ✅ | Anomaly detection, alerts | KQL scripts |
| Real-Time Dashboard | ✅ | Operations monitoring | KQL scripts |

## Analytics (Power BI)

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Semantic Models | ✅ | Sales + Operations models | Fabric CLI |
| Reports & Dashboards | ✅ | 4 interactive reports | Fabric CLI |
| OneLake Security (RLS) | ✅ | Row-level security | Terraform |
| OneLake Security (CLS) | ✅ | Column-level security | Terraform |
| Copilot | ✅ | AI-assisted analytics | Enabled on F8 |

## AI & Intelligence

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Data Agents (GA) | ⚠️ | Sales Analyst + Supply Chain | Config + Terraform |
| Fabric IQ + Ontology | ⚠️ | Contextual intelligence | Config |
| Fabric MCP AI Code Assistants | ⚠️ | Developer tooling | Enabled |
| Remote MCP Server | ⚠️ | AI agent execution | Config |

## Data Science & ML

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| MLflow Experiments | ✅ | 5 tracked experiments | Notebooks |
| Demand Forecasting | ✅ | Prophet time-series per store×category | MLflow |
| Customer Segmentation | ✅ | RFM + K-Means clustering | MLflow |
| Churn Prediction | ✅ | LightGBM classifier | MLflow |
| Promotion Effectiveness | ✅ | Propensity score matching / causal inference | MLflow |
| Anomaly Detection (ML) | ✅ | Isolation Forest on sales + inventory | MLflow |

## Data Activator / Reflex

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Inventory Alerts | ✅ | Low stock sustained trigger | Reflex + Power Automate |
| Sales Anomaly Alerts | ✅ | 3σ deviation detection | Reflex + Teams |
| IoT Failure Alerts | ✅ | Sensor silence + temperature | Reflex + Power Automate |
| Churn Risk Alerts | ✅ | VIP churn probability trigger | Reflex + Email |
| Promotion Performance | ✅ | Under/over-performing promos | Reflex + Email |

## Operational Database

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Fabric SQL Database | ✅ | OLTP POS system (normalized 3NF) | Terraform |
| CDC Extraction | ✅ | Change Data Capture → Lakehouse | Notebooks + Pipelines |
| POS Simulation | ✅ | sp_process_sale stored procedure | SQL |

## FabCon/SQLCon 2026 Features

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Graph in Fabric (GQL) | ⚠️ | Supply chain graph model | Terraform + GQL |
| Translytical Task Flows | ⚠️ | Write-back from Power BI | Config + UDFs |
| User Data Functions | ⚠️ | Serverless business logic | Python functions |
| Database Hub | ⚠️ | Unified DB management | Manual |
| Branched Workspaces | ⚠️ | Feature branching | Git integration |
| Bulk Import/Export APIs | ⚠️ | Mass artifact deployment | Scripts |
| Fabric CLI v1.5 CI/CD | ✅ | Single-command deploys | GitHub Actions |
| OneLake Catalog Search API | ⚠️ | Data discovery | REST API |
| Purview DSPM for AI | ⚠️ | AI security posture | Config |
| SQL Server 2025 Vectors | 📋 | RAG patterns | SQL scripts |
| Data Loss Prevention | ⚠️ | OneLake DLP policies | Config |

## DevOps & Automation

| Feature | Status | Demo Component | Automation |
|---------|--------|----------------|------------|
| Terraform Provider (GA) | ✅ | All infrastructure | GitHub Actions |
| Fabric CLI (GA) | ✅ | Content deployment | GitHub Actions |
| Deployment Pipelines | ✅ | Dev → Prod promotion | Terraform |
| GitHub Actions | ✅ | 5 workflow files | OIDC auth |
| Variable Library | 📋 | Environment configs | Terraform |

## Synthetic Data

| Dataset | Records | Format | Generator |
|---------|---------|--------|-----------|
| Customers | 2,000,000 | Parquet | gen_customers.py |
| Products | 25,000 | Parquet | gen_products.py |
| Stores | 500 | Parquet | gen_stores.py |
| Employees | 15,000 | Parquet | gen_hr_employees.py |
| Suppliers | 200 | Parquet | gen_supply_chain.py |
| Warehouses | ~20 | Parquet | gen_supply_chain.py |
| Sales Transactions | 200,000,000 | Parquet | gen_sales_transactions.py |
| Inventory Movements | 50,000,000 | Parquet | gen_inventory.py |
| Shipments | 2,000,000 | Parquet | gen_supply_chain.py |
| IoT Telemetry | 100,000,000 | Parquet | gen_iot_telemetry.py |
| Web Clickstream | 150,000,000 | Parquet | gen_clickstream.py |
| Customer Interactions | 10,000,000 | Parquet | gen_interactions.py |
| Promotions | 5,000 | Parquet | gen_promotions.py |
| Promotion Results | 20,000,000 | Parquet | gen_promotions.py |

## Real-Time Streams

| Stream | Events/sec | Generator |
|--------|-----------|-----------|
| POS Transactions | 5 | pos_transactions.ts |
| IoT Sensors | 10 | iot_sensors.ts |
| Inventory Updates | 2 | inventory_updates.ts |
