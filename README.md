# Fabric End-to-End Demo Environment

> **🚧 Work in Progress** — This project is under active development. Infrastructure modules, data generators, notebooks, and deployment workflows are being built out incrementally. Expect breaking changes, incomplete features, and rough edges. Contributions and feedback are welcome!

## Business Story

This demo simulates **Contoso Global Retail** — a multinational retailer with 500 stores across 8 countries. The environment runs an operational POS database, ingests data through a metadata-driven pipeline, transforms it through a medallion lakehouse, serves analytics via a star schema warehouse and Power BI, monitors operations in real-time, and uses ML to predict demand, segment customers, and detect anomalies. Every component is automated and deployed from code.

End-to-end Microsoft Fabric demo showcasing all platform capabilities including features announced at FabCon/SQLCon 2026 in Atlanta.

## Scenario

**Contoso Global Retail & Supply Chain** — a cross-industry demo with point-of-sale transactions, supply chain logistics, customer analytics, financial reporting, and workforce operations.

## Architecture

- **Fabric SQL Database (OLTP)**: Operational POS system with CDC extraction
- **Medallion Lakehouse**: Bronze → Silver → Gold with PySpark notebooks
- **Data Warehouse**: Star schema (dimensions + facts) with T-SQL
- **Real-Time Intelligence**: Eventhouse + KQL for streaming analytics
- **Power BI**: Semantic models, reports, dashboards, translytical task flows
- **Data Science (MLflow)**: Demand forecasting, segmentation, churn, anomaly detection
- **Data Activator (Reflex)**: Automated alerts for inventory, sales, IoT, and churn
- **Apache Airflow**: DAG-based orchestration (daily ETL, hourly quality, weekly maintenance)
- **Graph in Fabric**: Supply chain relationship modeling (GQL)
- **Data Agents**: AI-powered virtual analysts (sales + supply chain)
- **Automated Deployment**: Terraform + Fabric CLI + GitHub Actions

> **Data scale**: One variable (`FABRIC_SKU`) controls everything — from `F2` (~10M rows, 1 GB) for CI to `F64` (~5B rows, 375 GB) for stress-testing. Default is `F8` (~532M rows, 40 GB).

## Quick Start

> **📘 Complete Setup Guide:** For the full step-by-step walkthrough — prerequisites, secrets, variables, deployment order, post-deploy feature configuration, and verification — see **[SETUP.md](SETUP.md)**. It consolidates all setup information into one place.

```bash
# 1. Bootstrap (one-time): create SPN and configure permissions
cd infra/bootstrap && terraform init && terraform apply

# 2. Deploy infrastructure
make tf-init ENVIRONMENT=dev
make tf-plan ENVIRONMENT=dev
make tf-apply ENVIRONMENT=dev

# 3. Generate and upload demo data
make seed-data ENVIRONMENT=dev

# 4. Deploy content (notebooks, reports)
make deploy-content ENVIRONMENT=dev

# 5. Start real-time event generator
make stream-build
make stream-run
```

See [SETUP.md](SETUP.md) for the complete 7-step deployment with GitHub Actions alternatives, post-deployment Fabric feature configuration, admin portal settings, and verification checklist.

## Project Structure

```
infra/              Terraform modules and environment compositions
src/                Fabric content (notebooks, SQL, KQL, graphs, pipelines, Power BI)
data/generators/    Python synthetic data generators
streaming/          Node.js/TypeScript real-time event generator
scripts/            Deployment helper scripts
.github/workflows/  GitHub Actions CI/CD
docs/               Architecture, conventions, demo guide
```

## Feature Coverage

See [docs/feature-matrix.md](docs/feature-matrix.md) for full feature coverage including FabCon/SQLCon 2026 announcements.

## Prerequisites

- Azure subscription with Fabric capacity (F2+ — set `FABRIC_SKU` to match)
- Terraform >= 1.9
- Python >= 3.12
- Node.js >= 22
- Fabric CLI (`fab`)
- GitHub CLI (`gh`)

## Deployment Automation

| Layer | Tool | Trigger |
|-------|------|---------|
| Infrastructure | Terraform (`microsoft/fabric` provider) | `deploy-infra.yml` |
| Content | Fabric CLI v1.5 | `deploy-content.yml` |
| Data | Python generators + upload | `generate-data.yml` |
| Streaming | Docker + Container deployment | `deploy-streaming.yml` |
