# CI/CD Setup Guide

Everything you need to configure after cloning or forking this repository to get the GitHub Actions pipelines working.

> **Audience:** Developers, DevOps engineers, and automation agents setting up this project for the first time.

## Prerequisites

Before you begin, ensure you have:

- An **Azure subscription** with permissions to create App Registrations and Fabric capacity
- A **Microsoft Fabric F2+ capacity** (F8 recommended for the full demo)
- **GitHub CLI** (`gh`) installed — used by the bootstrap script ([install](https://cli.github.com/))
- **Azure CLI** (`az`) authenticated with Owner or Global Admin permissions ([install](https://aka.ms/install-azure-cli))
- **Terraform >= 1.5** installed locally (optional, only needed for local runs)

---

## 1. GitHub Environments

Create two environments in the repository settings (**Settings → Environments**):

| Environment | Purpose              | Recommended Protection Rules            |
|-------------|----------------------|-----------------------------------------|
| `dev`       | Development/testing  | None (auto-deploy)                      |
| `prod`      | Production demo      | Required reviewers, wait timer          |

All deployment workflows reference these environment names in their `environment:` fields. The `prod` environment gates (reviewers, wait timer) prevent accidental production changes — the `deploy-infra`, `deploy-content`, `deploy-streaming`, and `destroy` workflows all require environment approval before proceeding.

---

## 2. GitHub Secrets (Repository-level)

These are **sensitive values** that must be stored as repository secrets (**Settings → Secrets and variables → Actions → Secrets**):

| Secret | Description | How to Obtain |
|--------|-------------|---------------|
| `AZURE_CLIENT_ID` | Azure AD App Registration client/application ID | Created by `scripts/bootstrap.sh` or manually via **Azure Portal → App Registrations** |
| `AZURE_TENANT_ID` | Azure AD tenant ID | **Azure Portal → Azure Active Directory → Overview** |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID for resource provisioning | **Azure Portal → Subscriptions** |
| `EVENTHUB_CONNECTION_STRING` | Connection string for the Event Hub namespace used by the streaming generator | **Azure Portal → Event Hubs namespace → Shared access policies → RootManageSharedAccessKey** (created by Terraform after infra deploy) |

> **Note:** `GITHUB_TOKEN` is automatically provided by GitHub Actions — no manual configuration needed. The `deploy-streaming` workflow uses it to push Docker images to GHCR and to authenticate the container instance with the registry.

---

## 3. GitHub Variables (Repository-level)

These are **non-sensitive configuration values** stored as repository variables (**Settings → Secrets and variables → Actions → Variables**):

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `FABRIC_WORKSPACE_ID` | Fabric workspace ID for content deployment (notebooks, pipelines, reports) | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (GUID from Fabric portal URL) |
| `LAKEHOUSE_ONELAKE_URL` | OneLake URL for the Lakehouse where generated data is uploaded | `https://onelake.dfs.fabric.microsoft.com/<workspace-name>/<lakehouse-name>` |
| `AZURE_RESOURCE_GROUP` | Azure resource group for deploying the streaming container instance | `rg-contoso-fabric-dev` (created by Terraform) |

---

## 4. OIDC Federation (Azure ↔ GitHub)

The workflows use **OIDC (OpenID Connect)** for passwordless Azure authentication — no client secrets are stored. Every workflow that calls `azure/login@v2` requests an OIDC token via the `id-token: write` permission and exchanges it for an Azure access token.

### Automated setup (recommended)

The bootstrap script handles the entire OIDC configuration:

```bash
# Requires: Azure CLI (authenticated) + GitHub CLI (authenticated)
./scripts/bootstrap.sh
```

This script:

1. Creates an Azure AD App Registration (`fabric-e2e-demo-automation`)
2. Creates a Service Principal
3. Adds Fabric API permissions and grants admin consent
4. Configures OIDC federated credentials for the `dev` and `prod` environments
5. Assigns **Contributor** role on the subscription
6. Sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` as GitHub repository secrets

After running the script, you still need to complete these manual steps (printed at the end of the script output):

1. In **Azure Portal → Microsoft Fabric Admin Portal**: enable "Service principals can use Fabric APIs" and add the SP to a security group with Fabric access
2. In **GitHub → Settings → Environments**: create the `dev` and `prod` environments (see [Section 1](#1-github-environments))

### Manual setup

If you prefer to configure OIDC manually, create federated credentials in **Azure Portal → App Registration → Certificates & secrets → Federated credentials** with:

| Field    | Value                                                 |
|----------|-------------------------------------------------------|
| Issuer   | `https://token.actions.githubusercontent.com`         |
| Subject  | `repo:<owner>/<repo>:environment:dev`                 |
| Audience | `api://AzureADTokenExchange`                          |

Create a second credential with subject `repo:<owner>/<repo>:environment:prod`.

Then manually set the three GitHub secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`) as described in [Section 2](#2-github-secrets-repository-level).

---

## 5. Workflow Dispatch Inputs

All workflows can be triggered manually via **Actions → workflow → Run workflow**. The following inputs are available:

| Workflow | Input | Type | Options | Default | Description |
|----------|-------|------|---------|---------|-------------|
| **Deploy Infrastructure** | `environment` | choice | `dev`, `prod` | `dev` | Target environment |
| **Deploy Content** | `environment` | choice | `dev`, `prod` | `dev` | Target environment |
| **Deploy Content** | `content` | choice | `all`, `notebooks`, `pipelines`, `reports` | `all` | Which Fabric content to deploy |
| **Generate Data** | `environment` | choice | `dev`, `prod` | `dev` | Target environment (for upload) |
| **Generate Data** | `upload` | boolean | `true` / `false` | `false` | Whether to upload generated data to Lakehouse |
| **Deploy Streaming** | `environment` | choice | `dev`, `prod` | `dev` | Target environment |
| **🔴 Destroy Environment** | `environment` | choice | `dev`, `prod` | — | Environment to destroy |
| **🔴 Destroy Environment** | `confirmation` | string | — | — | Must type exactly `DESTROY` to confirm teardown |

Workflows also trigger automatically on push to `main`:

| Workflow | Auto-trigger Path |
|----------|-------------------|
| Deploy Infrastructure | `infra/**` |
| Deploy Content | `src/**` |
| Deploy Streaming | `streaming/**` |

---

## 6. Deployment Order

For first-time setup, follow this order:

```
1. bootstrap.sh          →  Azure identity + GitHub secrets
2. deploy-infra (dev)    →  Fabric capacity, workspaces, lakehouses, Event Hub
3. Set remaining secrets  →  EVENTHUB_CONNECTION_STRING (from Terraform output)
                             FABRIC_WORKSPACE_ID, LAKEHOUSE_ONELAKE_URL,
                             AZURE_RESOURCE_GROUP (from Terraform output or Azure Portal)
4. generate-data          →  Create synthetic data (set upload: true to push to Lakehouse)
5. deploy-content         →  Upload notebooks, pipelines, reports, semantic models
6. deploy-streaming       →  Build and deploy the real-time event generator to ACI
```

Step by step:

1. **Run `scripts/bootstrap.sh`** to create the Azure identity and set GitHub secrets (see [Section 4](#4-oidc-federation-azure--github)).

2. **Run the Deploy Infrastructure workflow** (target: `dev`) — this provisions Fabric capacity, workspaces, lakehouses, Event Hubs, and other Azure resources via Terraform.

3. **Set remaining secrets and variables** — after infra is deployed, grab the outputs (Event Hub connection string, workspace ID, Lakehouse URL, resource group name) and configure them as described in [Sections 2](#2-github-secrets-repository-level) and [3](#3-github-variables-repository-level).

4. **Run the Generate Data workflow** with `upload: true` — creates synthetic Parquet datasets and uploads them to the Lakehouse bronze layer via `azcopy`.

5. **Run the Deploy Content workflow** — uploads notebooks (bronze/silver/gold), Data Factory pipeline definitions, semantic models, and Power BI reports to the Fabric workspace.

6. **Run the Deploy Streaming workflow** — builds the Node.js streaming generator, pushes a Docker image to GHCR, and deploys it to Azure Container Instances.

7. **(Optional)** Repeat steps 2–6 targeting the `prod` environment.

---

## 7. Terraform State Backend

Terraform state is stored in an **Azure Storage Account** with an `azurerm` backend. The backend configuration lives in:

- `infra/environments/dev/backend.tf`
- `infra/environments/prod/backend.tf`

### If you fork this repository

You **must** update these files with your own storage account details. The current values point to the original author's storage account and will fail for your subscription.

Replace the values in both `backend.tf` files:

```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "<your-resource-group>"
    storage_account_name = "<your-storage-account>"
    container_name       = "tfstate"
    key                  = "fabric-e2e-dev.tfstate"   # or prod
    subscription_id      = "<your-subscription-id>"
  }
}
```

Also update the matching `-backend-config` values in the workflow files (`deploy-infra.yml`, `destroy.yml`) if you use runtime overrides — currently these are hardcoded in the `terraform init` steps.

### Create the state backend storage

If you don't already have a storage account for Terraform state:

```bash
az group create -n rg-terraform-state -l eastus
az storage account create -n <unique-name> -g rg-terraform-state -l eastus --sku Standard_LRS
az storage container create -n tfstate --account-name <unique-name>
```

> **Tip:** Storage account names must be globally unique. Use a random suffix like `sttfstate$(openssl rand -hex 2)`.

---

## Troubleshooting

### "OIDC token request failed"

The federated credential `subject` must match your repository name exactly, including the owner (case-sensitive). Verify in **Azure Portal → App Registration → Certificates & secrets → Federated credentials** that the subject is `repo:<owner>/<repo>:environment:<env>`.

### "Terraform state lock"

Another workflow may be running against the same environment. Check the **Actions** tab for in-progress runs. If a run was cancelled mid-apply, you may need to manually force-unlock:

```bash
cd infra/environments/dev
terraform init
terraform force-unlock <lock-id>
```

### "Fabric workspace not found"

Verify that the `FABRIC_WORKSPACE_ID` variable is set correctly (must be a GUID, not a workspace name). Also confirm the deploying service principal has access to the workspace — in the Fabric portal, add the SPN to the workspace with at least **Member** role.

### "Event Hub connection refused"

The `EVENTHUB_CONNECTION_STRING` secret may be stale after an infrastructure re-deploy (Terraform may recreate the namespace). Re-copy the connection string from **Azure Portal → Event Hubs namespace → Shared access policies → RootManageSharedAccessKey** and update the GitHub secret.

### "Container image pull failed" (deploy-streaming)

The `deploy-streaming` workflow pushes to GitHub Container Registry (GHCR). Ensure the repository's package visibility allows the Azure Container Instance to pull. If your repo is private, the ACI deploy step already passes `GITHUB_TOKEN` as registry credentials — verify the token has `packages:read` scope.

---

## Related Documentation

- [README.md](../README.md) — Project overview, architecture, and quick start
- [Demo Guide](demo-guide.md) — Step-by-step walkthrough of the full demo scenario
- [Architecture](architecture.md) — System design and component relationships
- [Secrets Policy](secrets-policy.md) — How secrets are managed in this project
- [Conventions](conventions.md) — Coding and naming conventions
