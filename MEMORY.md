# Project Memory

This file captures project learnings that persist across agent sessions.

## Project Overview

- **Name**: Fabric End-to-End Demo Environment
- **Scenario**: Contoso Global Retail & Supply Chain
- **Fabric Capacity**: F8
- **Environments**: Dev + Prod (per-workload workspaces × lifecycle stages)

## Tech Stack

- **Infrastructure**: Terraform (microsoft/fabric v1.8.0+, hashicorp/azurerm, hashicorp/azuread)
- **Data Engineering**: PySpark notebooks (medallion: bronze → silver → gold)
- **Data Warehouse**: Fabric Warehouse (T-SQL, star schema)
- **Real-Time**: Eventhouse + KQL + Eventstream
- **Analytics**: Power BI (PBIP format, semantic models, translytical task flows)
- **Graph**: Fabric Graph (GQL)
- **AI**: Data Agents (sales analyst, supply chain advisor)
- **Streaming**: Node.js/TypeScript event generator
- **Data Generation**: Python (Faker + Pandas)
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

## Active Context

- Initial implementation in progress
- Phases 0-7 defined in plan
