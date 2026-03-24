# Complete Setup Guide

> Everything you need to get the **Contoso Global Retail** demo environment running — from zero to a fully operational Fabric environment.

**Estimated total setup time:** ~2 hours for first-time deployment (varies with data scale and network speed).

Once setup is complete, see the [Demo Guide](docs/demo-guide.md) for presenting the six-act walkthrough.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Repository Setup](#2-repository-setup)
3. [GitHub Configuration](#3-github-configuration)
4. [Bootstrap (Azure Identity)](#4-bootstrap-azure-identity)
5. [Deployment Order](#5-deployment-order)
6. [Post-Deployment Feature Configuration](#6-post-deployment-feature-configuration)
7. [Fabric Admin Portal Settings](#7-fabric-admin-portal-settings)
8. [Data Scale Options](#8-data-scale-options)
9. [Verification Checklist](#9-verification-checklist)
10. [Troubleshooting](#10-troubleshooting)
11. [Teardown](#11-teardown)

---

## 1. Prerequisites

| Requirement | Minimum | Recommended | Install Link |
|-------------|---------|-------------|--------------|
| Azure subscription | Permissions to create App Registrations and Fabric capacity | Owner or Global Admin for bootstrap | [Azure Portal](https://portal.azure.com) |
| Microsoft Fabric capacity | F2 | F8+ (profile scales to F64) | [Fabric pricing](https://www.microsoft.com/microsoft-fabric/pricing) |
| Terraform | >= 1.9 | Latest | [terraform.io/downloads](https://www.terraform.io/downloads) |
| Python | >= 3.12 with pip | Latest | [python.org](https://www.python.org/downloads/) |
| Node.js | >= 22 with npm | LTS | [nodejs.org](https://nodejs.org/) |
| Fabric CLI (`fab`) | Latest | Latest | [Fabric CLI docs](https://learn.microsoft.com/fabric/cicd/fabric-cli) |
| GitHub CLI (`gh`) | Latest | Latest | [cli.github.com](https://cli.github.com/) |
| Azure CLI (`az`) | Latest, authenticated | Latest | [aka.ms/install-azure-cli](https://aka.ms/install-azure-cli) |
| Docker | Latest | Latest | [docker.com](https://www.docker.com/get-started/) |

> **Docker** is required for the IoT streaming simulator container. If you only need batch data, you can skip it initially.

---

## 2. Repository Setup

### Clone or fork

```bash
# Fork via GitHub CLI (recommended — gives you your own repo for CI/CD)
gh repo fork <owner>/fabric-end-2-end --clone

# Or clone directly
git clone https://github.com/<owner>/fabric-end-2-end.git
cd fabric-end-2-end
```

### Install local dependencies

```bash
make setup
```

This installs Python requirements (`data/generators/requirements.txt`) and Node.js dependencies (`streaming/`).

### Update the Terraform state backend

> **⚠️ Required if you fork.** The `backend.tf` files point to the original author's storage account and will fail for your subscription.

Edit both backend files with your own storage account details:

- `infra/environments/dev/backend.tf`
- `infra/environments/prod/backend.tf`

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "<your-resource-group>"
    storage_account_name = "<your-storage-account>"
    container_name       = "tfstate"
    key                  = "fabric-e2e-dev.tfstate"   # use "fabric-e2e-prod.tfstate" for prod
    subscription_id      = "<your-subscription-id>"
  }
}
```

### Create a Terraform state storage account (if you don't have one)

```bash
# Pick a unique name — storage accounts are globally unique
STATE_ACCOUNT="sttfstate$(openssl rand -hex 2)"

az group create -n rg-terraform-state -l eastus
az storage account create -n "$STATE_ACCOUNT" -g rg-terraform-state -l eastus --sku Standard_LRS
az storage container create -n tfstate --account-name "$STATE_ACCOUNT"

echo "Storage account: $STATE_ACCOUNT"
# Use this name in backend.tf and the TF_STATE_STORAGE_ACCOUNT GitHub secret
```

---

## 3. GitHub Configuration

### 3a. Environments

Create two environments in **Settings → Environments**:

| Environment | Purpose | Protection Rules |
|-------------|---------|-----------------|
| `dev` | Development and testing | None (auto-deploy) |
| `prod` | Production demo | Required reviewers, wait timer |

All deployment workflows reference these environment names. The `prod` environment gates prevent accidental production changes.

### 3b. Secrets (Repository-level)

Configure in **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Description | How to Obtain |
|--------|-------------|---------------|
| `AZURE_CLIENT_ID` | App Registration client/application ID | Created by `scripts/bootstrap.sh` (see [Section 4](#4-bootstrap-azure-identity)) |
| `AZURE_TENANT_ID` | Azure AD tenant ID | **Azure Portal → Entra ID → Overview** |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID for resource provisioning | **Azure Portal → Subscriptions** |
| `TF_STATE_STORAGE_ACCOUNT` | Terraform state storage account name | The storage account you created above (e.g., `sttfstate7a2b`) |
| `TF_STATE_CONTAINER` | Terraform state blob container name | Usually `tfstate` |
| `TF_STATE_RESOURCE_GROUP` | Resource group containing the TF state storage account | e.g., `rg-terraform-state` |
| `EVENTHUB_CONNECTION_STRING` | Event Hub connection string for IoT streaming | From Terraform output after infra deploy (Step 2) |

> **Note:** `GITHUB_TOKEN` is provided automatically by GitHub Actions — no manual setup needed. The first three secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) are set automatically by `bootstrap.sh` if GitHub CLI is authenticated.

### 3c. Variables (Repository-level)

Configure in **Settings → Secrets and variables → Actions → Variables**:

| Variable | Description | When Available |
|----------|-------------|----------------|
| `FABRIC_WORKSPACE_ID` | Fabric workspace GUID for content deployment | After infra deploy — from Terraform output or Fabric portal URL |
| `LAKEHOUSE_ONELAKE_URL` | OneLake URL for data upload | After infra deploy — `https://onelake.dfs.fabric.microsoft.com/<workspace>/<lakehouse>` |
| `AZURE_RESOURCE_GROUP` | Resource group for streaming ACI deployment | After infra deploy — e.g., `rg-contoso-fabric-dev` |
| `FABRIC_SKU` | Fabric capacity SKU — controls capacity size AND data generation scale (F2/F4/F8/F16/F32/F64) | F8 |

---

## 4. Bootstrap (Azure Identity)

The bootstrap creates the Azure identity that Terraform and GitHub Actions use to manage Fabric resources.

### Option A: Shell script (recommended)

```bash
# Requires: az (authenticated) + gh (authenticated)
./scripts/bootstrap.sh
```

### Option B: Terraform bootstrap

```bash
cd infra/bootstrap
terraform init
terraform apply -var="subscription_id=<your-sub-id>" \
                -var="resource_group_name=<your-app-rg>" \
                -var="state_resource_group_name=<your-state-rg>"
```

### What bootstrap creates

- **Azure AD App Registration** (`fabric-e2e-demo-automation` / `sp-fabric-terraform-automation`)
- **Service Principal** with Fabric API permissions
- **OIDC federated credentials** for the `dev` and `prod` GitHub environments
- **Contributor role assignment** scoped to your resource group(s)
- Automatically sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as GitHub secrets (shell script only)

### Manual post-bootstrap steps

These cannot be automated and must be done in the portal:

1. **Fabric Admin Portal → Tenant settings → Developer settings:**
   - Enable **"Service principals can use Fabric APIs"**
   - Add the service principal to a security group with Fabric access

2. **GitHub → Settings → Environments:**
   - Create `dev` and `prod` environments (if not already done in [Section 3a](#3a-environments))
   - Add required reviewers to `prod`

---

## 5. Deployment Order

> **One-command deployment:** `make deploy-all ENVIRONMENT=dev` runs the full pipeline below.
> For step-by-step control, follow the individual steps.

### Step 0: Preflight Check + Tenant Configuration

Before deploying, validate all prerequisites and configure tenant settings:

```bash
# Validate tools, auth, and settings
make preflight ENVIRONMENT=dev

# Enable required Fabric Admin tenant settings (one-time, requires Fabric Admin)
make configure-tenant

# Or with a security group scope (recommended for production):
./scripts/configure-tenant.sh --security-group <entra-group-id>
```

The preflight check validates: CLI tools, Azure/Fabric auth, tenant settings, TF state backend, GitHub secrets (in CI), and Python/Node.js dependencies.

The tenant configuration script enables these settings via the Admin REST API (Preview):
1. Service principals can use Fabric APIs
2. Push apps to end users
3. Digital Twin Builder (Preview)
4. Users can create Fabric items
5. XMLA endpoints

> **Note:** `configure-tenant.sh` uses the Preview Update Tenant Settings API. If any setting fails to enable programmatically, the script provides manual fallback instructions.

```
Step 1: Bootstrap           → Azure identity + GitHub secrets
Step 2: Deploy Infra (dev)  → Fabric capacity, workspaces, lakehouses, Event Hub
Step 3: Set post-deploy     → EVENTHUB_CONNECTION_STRING, FABRIC_WORKSPACE_ID,
        secrets/variables      LAKEHOUSE_ONELAKE_URL, AZURE_RESOURCE_GROUP
Step 4: Generate Data       → 532M+ rows of synthetic Parquet data
Step 5: Deploy Fabric Items → Eventstreams, dashboards, dataflows, GraphQL, etc.
Step 6: Deploy Streaming    → IoT simulator to Azure Container Instances
Step 7: Post-Deploy Config  → Domains, Variable Library, Airflow, PBI Apps
Step 8: Start OLTP Sim      → Continuous POS transactions to SQL Database
```

### Step 1: Bootstrap

See [Section 4](#4-bootstrap-azure-identity). This is a one-time setup.

### Step 2: Deploy Infrastructure

This provisions Fabric capacity, 8 workspaces, lakehouses, warehouse, Eventhouse, Event Hub, SQL Database, and all supporting resources via Terraform.

| Method | Commands |
|--------|----------|
| **Local** | `make tf-init ENVIRONMENT=dev` → `make tf-plan ENVIRONMENT=dev` → `make tf-apply ENVIRONMENT=dev` |
| **GitHub Actions** | **Actions → Deploy Infrastructure → Run workflow** → select `dev` |
| **Auto-trigger** | Push to `infra/**` on `main` |

### Step 3: Set Post-Deploy Secrets and Variables

After Terraform completes, grab the outputs and configure GitHub:

```bash
# From Terraform output:
cd infra/environments/dev
terraform output -raw eventhub_connection_string
terraform output -raw workspace_id
terraform output -raw lakehouse_onelake_url
terraform output -raw resource_group_name
```

Set these values:

| Target | Name | Source |
|--------|------|--------|
| Secret | `EVENTHUB_CONNECTION_STRING` | Terraform output or **Azure Portal → Event Hubs → Shared access policies** |
| Variable | `FABRIC_WORKSPACE_ID` | Terraform output or Fabric portal workspace URL |
| Variable | `LAKEHOUSE_ONELAKE_URL` | Terraform output |
| Variable | `AZURE_RESOURCE_GROUP` | Terraform output |

### Step 4: Generate Data

Creates synthetic Parquet datasets and uploads them to the Lakehouse bronze layer.

| Method | Commands |
|--------|----------|
| **Local (generate only)** | `make generate-data` |
| **Local (generate + upload)** | `make seed-data ENVIRONMENT=dev` |
| **GitHub Actions** | **Actions → Generate Data → Run workflow** → select `dev`, set `upload: true` |

> **Tip:** Use `--scale small` for a quick 5-minute test run. See [Section 8](#8-data-scale-options) for scale profiles.

### Step 5: Deploy Content

Uploads notebooks, pipeline definitions, semantic models, and Power BI reports to the Fabric workspace.

| Method | Commands |
|--------|----------|
| **Local** | `make deploy-content ENVIRONMENT=dev` |
| **GitHub Actions** | **Actions → Deploy Content → Run workflow** → select `dev`, content: `all` |
| **Auto-trigger** | Push to `src/**` on `main` |

You can also deploy selectively:

```bash
make upload-notebooks ENVIRONMENT=dev   # Notebooks only
make upload-reports ENVIRONMENT=dev     # Reports only
```

### Step 6: Deploy Streaming (IoT Simulator)

Builds the Node.js streaming generator Docker image and deploys it to Azure Container Instances.

| Method | Commands |
|--------|----------|
| **Local (build)** | `make stream-docker` |
| **Local (run dry)** | `make stream-run` |
| **GitHub Actions** | **Actions → Deploy Streaming → Run workflow** → select `dev` |
| **Auto-trigger** | Push to `streaming/**` on `main` |

### Step 7: Start OLTP Simulator

Generates continuous POS transactions against the Fabric SQL Database.

```bash
# Dry run (no database, logs to console)
make sim-run

# Live against the deployed SQL Database
make sim-run-live
```

> The OLTP simulator feeds Change Data Capture, which drives the bronze → silver → gold pipeline.

---

## 6. Post-Deployment Feature Configuration

These features require **manual configuration in the Fabric portal** after infrastructure is deployed. They are not (yet) fully automatable via Terraform.

### 6a. Real-Time Hub

Register and manage all data streams through the tenant-wide Real-Time Hub.

1. Enable **Change Event Streaming** on SQL Database tables:
   - `dbo.Transactions`, `dbo.TransactionItems`, `dbo.Inventory`, `dbo.CustomerInteractions`
2. Verify IoT streams are flowing from the simulator → Event Hub → Eventstream
3. Open **Real-Time Hub** in the Fabric portal and register all 5 streams
4. Connect downstream consumers (KQL dashboards, Data Activator alerts)

📖 **Full guide:** [`src/realtime-hub/hub_setup_guide.md`](src/realtime-hub/hub_setup_guide.md)

### 6b. Database Mirroring

Replicate external databases into OneLake with near-real-time CDC.

1. Create **Fabric Connections** for each external source:
   - Azure SQL (ERP): `Suppliers`, `PurchaseOrders`, `GLJournalEntries`, etc.
   - Snowflake (partner data): `supplier_performance_metrics`, `raw_material_prices`, etc.
   - Cosmos DB: `product_catalog`, `customer_profiles`
2. Create **Mirrored Databases** in the ingestion workspace
3. Configure replication mode as **Continuous** for each mirror
4. Verify CDC is active and data is landing in the Lakehouse

📖 **Full guide:** [`src/mirroring/mirror_setup_guide.md`](src/mirroring/mirror_setup_guide.md)

### 6c. GraphQL API

Expose warehouse data through a unified GraphQL endpoint.

1. In the `contoso-data-warehouse-{env}` workspace, create a **GraphQL API** item (`contoso_retail_api`)
2. Connect it to the `contoso_warehouse` data source
3. Import the schema from [`src/graphql/schema/retail_api.graphql`](src/graphql/schema/retail_api.graphql)
4. Configure authentication (Entra ID — interactive or client credentials)
5. Test with the built-in GraphQL explorer

📖 **Full guide:** [`src/graphql/docs/graphql_setup.md`](src/graphql/docs/graphql_setup.md)

### 6d. Digital Twin Builder (Preview)

Create live digital replicas of stores and supply chain assets.

1. Enable **Digital Twin Builder (Preview)** in Fabric Admin Portal → Tenant settings
2. Create twin spaces in the `contoso-real-time-{env}` workspace:
   - `contoso_store_twin` — retail store layout + equipment
   - `contoso_supply_chain_twin` — supplier → warehouse → store network
3. Import entity type models from [`src/digital-twins/`](src/digital-twins/)
4. Link telemetry bindings to the Eventhouse KQL database

📖 **Full guide:** [`src/digital-twins/twin_setup_guide.md`](src/digital-twins/twin_setup_guide.md)

### 6e. Apache Airflow

Production-grade DAG orchestration for the full data platform.

1. Create an **Apache Airflow Job** in the data-engineering workspace
2. Upload DAG files from [`src/airflow/dags/`](src/airflow/dags/)
3. Install requirements from [`src/airflow/requirements.txt`](src/airflow/requirements.txt)
4. Set Airflow Variables (see below)
5. Enable DAGs — they are paused by default

<details>
<summary><strong>Full Airflow Variables list (click to expand)</strong></summary>

Set these in **Apache Airflow Jobs → Environment → Variables** or via `airflow variables import`:

| Variable | Description |
|----------|-------------|
| `fabric_workspace_id` | Data-engineering workspace ID |
| `fabric_warehouse_workspace_id` | Data-warehouse workspace ID |
| `fabric_realtime_workspace_id` | Real-time analytics workspace ID |
| `fabric_datascience_workspace_id` | Data-science workspace ID |
| `notebook_ingest_sqldb` | CDC extraction notebook item ID |
| `notebook_ingest_dimensions` | `ingest_dimensions.py` notebook ID |
| `notebook_ingest_sales` | `ingest_sales.py` notebook ID |
| `notebook_ingest_inventory` | `ingest_inventory.py` notebook ID |
| `notebook_transform_sales` | `transform_sales.py` notebook ID |
| `notebook_transform_customers` | `transform_customers.py` notebook ID |
| `notebook_transform_supply` | `transform_supply_chain.py` notebook ID |
| `notebook_dim_customer` | `dim_customer.py` notebook ID |
| `notebook_dim_product` | `dim_product.py` notebook ID |
| `notebook_dim_store` | `dim_store.py` notebook ID |
| `notebook_fact_sales` | `fact_sales.py` notebook ID |
| `notebook_fact_inventory` | `fact_inventory.py` notebook ID |
| `pipeline_load_warehouse` | `pl_load_warehouse` pipeline item ID |
| `notebook_ml_forecast` | Demand forecasting notebook ID |
| `notebook_ml_churn` | Churn prediction notebook ID |
| `notebook_ml_segments` | Customer segmentation notebook ID |
| `kql_database_id` | Eventhouse KQL database ID |
| `quality_alert_webhook` | Microsoft Teams incoming-webhook URL |
| `mlflow_tracking_uri` | MLflow tracking server URI |
| `retention_days` | Hot-storage retention period (default: `365`) |

All IDs are GUIDs from the Fabric portal URL or Terraform outputs.

</details>

📖 **Full guide:** [`src/airflow/README.md`](src/airflow/README.md)

### 6f. Power BI Apps

Bundle reports into installable app packages for end users.

1. Enable **"Push apps to end users"** in Power BI Admin Portal → Tenant settings
2. Create Entra ID security groups for target audiences:
   - Store Managers, Regional Directors, VP Operations
   - C-Suite, SVP Leadership
   - Technicians, Drivers, Warehouse Workers
3. Publish 3 apps from the `contoso-analytics-{env}` workspace:
   - **Contoso Retail Operations** — daily operations and inventory
   - **Contoso Executive Suite** — C-level dashboards (Highly Confidential)
   - **Contoso Field Operations** — mobile-optimized for field workers

📖 **Full guide:** [`src/power-bi/apps/app_setup_guide.md`](src/power-bi/apps/app_setup_guide.md)

### 6g. Deployment Pipelines (Native Fabric)

Promote Fabric item content across Dev → Test → Prod stages.

1. Create **4 deployment pipelines** in the Fabric portal:
   - Retail Data Pipeline
   - Analytics & Reporting
   - Real-Time Intelligence
   - AI & Data Science
2. Assign workspace stages (Dev → Test → Prod) to each pipeline
3. Configure deployment rules and approval gates per the config in
   [`src/governance/deployment_pipeline_config.json`](src/governance/deployment_pipeline_config.json)

📖 **Full guide:** [`src/governance/deployment_pipeline_setup.md`](src/governance/deployment_pipeline_setup.md)

### 6h. Scorecards

Create Power BI scorecards for goal tracking.

1. In the `contoso-analytics-{env}` workspace, create scorecards using definitions from
   [`src/power-bi/scorecards/`](src/power-bi/scorecards/):
   - `retail_operations_scorecard.json`
   - `supply_chain_scorecard.json`
   - `digital_analytics_scorecard.json`
2. Connect each goal to the corresponding semantic model measure
3. Assign goal owners from the appropriate security groups

### 6i. Domains

Organize workspaces into business domains for decentralized governance.

Configure **4 business domains** in Fabric Admin Portal → Domains:

| Domain | Workspaces |
|--------|------------|
| **Retail Operations** | `contoso-ingestion-{env}`, `contoso-data-engineering-{env}`, `contoso-data-warehouse-{env}` |
| **Customer Intelligence** | `contoso-data-science-{env}`, `contoso-analytics-{env}` |
| **Supply Chain & Logistics** | `contoso-real-time-{env}` |
| **Corporate Governance** | `contoso-governance-{env}`, `contoso-ai-agents-{env}` |

📖 **Domain configuration:** [`src/governance/domain_config.json`](src/governance/domain_config.json)

### 6j. Variable Library

Centralize environment-specific configuration values.

1. Create a **Variable Library** in the `contoso-governance-{env}` workspace
2. Import variables from [`src/governance/variable_library/`](src/governance/variable_library/):
   - `environment_variables.json` — environment-specific settings
   - `connection_references.json` — connection string references
   - `feature_flags.json` — feature toggles
3. Link the Variable Library to deployment pipelines for environment-aware configuration

---

## 7. Fabric Admin Portal Settings

These tenant settings are required for the full demo. They can be enabled **automatically** or manually.

### Automated (recommended)

```bash
# Enable all required tenant settings via REST API
make configure-tenant

# Or with dry-run to see what would change:
./scripts/configure-tenant.sh --dry-run

# Scope SPN access to a specific security group (recommended for production):
./scripts/configure-tenant.sh --security-group <entra-group-id>
```

The script uses the Fabric Admin REST API (Preview) and requires the authenticated identity to be a **Fabric Administrator** with `Tenant.ReadWrite.All` permission.

### Manual fallback

If the API fails for any setting, enable it in the portal:

| Setting | Location | Required For |
|---------|----------|-------------|
| Service principals can use Fabric APIs | Admin Portal → Tenant settings → Developer settings | All Terraform / CI/CD deployment |
| Push apps to end users | Admin Portal → Tenant settings → Content pack and app settings | Power BI Apps auto-install |
| Digital Twin Builder (Preview) | Admin Portal → Tenant settings → Preview features | Digital Twin Builder |
| Users can create Fabric items | Admin Portal → Tenant settings | Content deployment |
| Allow XMLA endpoints | Admin Portal → Capacity settings | Semantic model refresh via external tools |

### Verify settings

```bash
# Run preflight check to verify all settings are enabled
make preflight ENVIRONMENT=dev
```

---

## 8. Data Scale Options

The data generators support a `--scale` flag named after the Fabric capacity SKU they target. Choose the profile matching your provisioned capacity:

| Profile | Approximate Rows | Parquet Size | Generation Time | Target Capacity |
|---------|-----------------|-------------|-----------------|-----------------|
| `f2` | ~10M | ~1 GB | ~5 min | F2 |
| `f4` | ~50M | ~4 GB | ~20 min | F4 |
| `f8` | ~532M | ~40 GB | ~3 hours | F8 |
| `f16` | ~1B | ~80 GB | ~6 hours | F16 |
| `f32` | ~3B | ~225 GB | ~16 hours | F32 |
| `f64` | ~5B | ~375 GB | ~24+ hours | F64 |

```bash
# Local — generate small dataset for CI
python data/generators/generate_all.py --output-dir data/generators/output --scale f2

# Local — generate standard demo data (default)
make seed-data ENVIRONMENT=dev FABRIC_SKU=F8

# Local — generate enterprise-scale data
make generate-data FABRIC_SKU=F32
```

> **In CI**, set `FABRIC_SKU` as a GitHub repository variable. All workflows will use it automatically.
>
> **Out of memory?** Use `--scale f2` or `--scale f4`. Profiles `f16` and above generate billions of rows and require 32+ GB RAM. Consider generating on a VM with matching resources.

---

## 9. Verification Checklist

After completing all deployment steps, walk through this checklist to confirm everything is working:

- [ ] ✅ Terraform apply succeeded — all modules green, no errors
- [ ] ✅ **8 Fabric workspaces** visible in portal (`contoso-ingestion-dev`, `contoso-data-engineering-dev`, `contoso-data-warehouse-dev`, `contoso-real-time-dev`, `contoso-data-science-dev`, `contoso-analytics-dev`, `contoso-governance-dev`, `contoso-ai-agents-dev`)
- [ ] ✅ Lakehouse contains **bronze / silver / gold** Delta tables with data
- [ ] ✅ Warehouse has **dimension and fact tables** populated (`dim_customer`, `dim_product`, `dim_store`, `fact_sales`, `fact_inventory`)
- [ ] ✅ KQL database receiving events from Eventstream — run `.show database contoso_kqldb extents` to verify
- [ ] ✅ IoT simulator running — check ACI container status in Azure Portal or run `az container show`
- [ ] ✅ OLTP simulator generating transactions — verify CDC watermark timestamps are advancing
- [ ] ✅ Power BI reports loading with data — open `executive_dashboard` and `sales_analytics` reports
- [ ] ✅ Airflow DAGs scheduled and running — check Airflow UI for `contoso_daily_etl`, `contoso_hourly_realtime_quality`, `contoso_weekly_maintenance`
- [ ] ✅ Data Activator alerts configured — verify Reflex triggers for inventory, sales anomaly, IoT failure, churn risk
- [ ] ✅ ML models trained and registered in MLflow — check experiments for demand forecasting, churn, and segmentation

---

## 10. Troubleshooting

### "OIDC token request failed"

The federated credential `subject` must match your repository name exactly (case-sensitive).

**Fix:** Verify in **Azure Portal → App Registration → Certificates & secrets → Federated credentials** that the subject is `repo:<owner>/<repo>:environment:<env>`.

### Terraform state lock

Another workflow or local session is holding the state lock.

**Fix:** Check the **Actions** tab for in-progress runs. If a run was cancelled mid-apply:

```bash
cd infra/environments/dev
terraform init
terraform force-unlock <lock-id>
```

### "Fabric workspace not found"

**Fix:** Verify `FABRIC_WORKSPACE_ID` is a GUID (not a workspace name). Confirm the service principal has at least **Member** role on the workspace in the Fabric portal.

### Event Hub connection refused

The `EVENTHUB_CONNECTION_STRING` may be stale after an infrastructure re-deploy.

**Fix:** Re-copy from **Azure Portal → Event Hubs namespace → Shared access policies → RootManageSharedAccessKey** and update the GitHub secret.

### Container image pull failed (deploy-streaming)

**Fix:** Ensure the repository's package visibility allows the Azure Container Instance to pull from GHCR. For private repos, verify the `GITHUB_TOKEN` has `packages:read` scope.

### Data generation out of memory

**Fix:** Use `--scale small` or `--scale medium`. The `full` profile requires ~16 GB RAM for the 200M sales transaction generator.

```bash
python data/generators/generate_all.py --output-dir data/generators/output --scale small
```

### Notebook execution fails

**Fix:** Check that the Lakehouse mount path is correct. Notebooks reference the Lakehouse by name — verify `lh_bronze`, `lh_silver`, `lh_gold` exist in the `contoso-data-engineering-{env}` workspace. Ensure data was uploaded before running silver/gold transforms.

### KQL query returns no data

**Fix:** Verify the Eventstream is **activated** (open Eventstream → click **Activate**). Check that the IoT simulator or OLTP simulator is running. Run `.show ingestion failures` in the KQL database to diagnose ingestion issues.

---

## 11. Teardown

### GitHub Actions

1. Go to **Actions → 🔴 Destroy Environment → Run workflow**
2. Select the environment (`dev` or `prod`)
3. Type `DESTROY` in the confirmation field
4. Run — this executes `terraform destroy` with environment approval

### Local

```bash
make tf-destroy ENVIRONMENT=dev
```

### Manual cleanup

The following items are **not managed by Terraform** and must be removed manually if you want a full cleanup:

- Fabric Connections (created in portal for mirroring)
- Apache Airflow Jobs and DAG configurations
- Power BI Apps (published to the app marketplace)
- Digital Twin Builder twin spaces
- GraphQL API items
- Scorecards and deployment pipeline stage assignments
- Domain assignments in Fabric Admin Portal
- Variable Library items

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Project overview, architecture, and quick start |
| [docs/demo-guide.md](docs/demo-guide.md) | Step-by-step walkthrough for presenting the six-act demo |
| [docs/feature-matrix.md](docs/feature-matrix.md) | Full feature coverage matrix including FabCon/SQLCon 2026 features |
| [docs/architecture.md](docs/architecture.md) | System design, data flow diagrams, and deployment architecture |
| [docs/cicd-setup.md](docs/cicd-setup.md) | CI/CD deep dive — OIDC federation, workflow dispatch inputs, auto-triggers |

> **`docs/cicd-setup.md`** still exists for CI/CD-specific deep dives (OIDC manual setup, workflow dispatch inputs, auto-trigger paths). **This file (`SETUP.md`) is the primary reference** for getting the environment running end to end.
