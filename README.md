# Fabric End-to-End Demo Environment

> **🚧 Work in Progress** — This project is under active development. Infrastructure modules, data generators, notebooks, and deployment workflows are being built out incrementally. Expect breaking changes, incomplete features, and rough edges. Contributions and feedback are welcome!

End-to-end Microsoft Fabric demo showcasing all platform capabilities including features announced at FabCon/SQLCon 2026 in Atlanta.

## Scenario

**Contoso Global Retail & Supply Chain** — a cross-industry demo with point-of-sale transactions, supply chain logistics, customer analytics, financial reporting, and workforce operations.

## Architecture

- **Medallion Lakehouse**: Bronze → Silver → Gold with PySpark notebooks
- **Data Warehouse**: Star schema (dimensions + facts) with T-SQL
- **Real-Time Intelligence**: Eventhouse + KQL for streaming analytics
- **Power BI**: Semantic models, reports, dashboards, translytical task flows
- **Graph in Fabric**: Supply chain relationship modeling (GQL)
- **Data Agents**: AI-powered virtual analysts (sales + supply chain)
- **Automated Deployment**: Terraform + Fabric CLI + GitHub Actions

## Quick Start

> **CI/CD Setup:** For detailed configuration of GitHub Actions pipelines — including required secrets, variables, OIDC federation, and deployment order — see the [CI/CD Setup Guide](docs/cicd-setup.md).

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

- Azure subscription with Fabric F8 capacity
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
