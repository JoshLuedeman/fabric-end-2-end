# Fabric Deployment Pipelines — Setup Guide

## Overview

Contoso Global Retail uses **two complementary CI/CD mechanisms**:

| Concern | Tool | What it manages |
|---|---|---|
| **Infrastructure-as-Code** | GitHub Actions + Terraform | Fabric capacity, workspaces, lakehouses, warehouses, connections, eventstreams |
| **Fabric Item Promotion** | Fabric Deployment Pipelines | Promoting item *content* (data, semantic models, reports, notebooks) across Dev → Test → Prod workspaces |

These are **not competing** approaches — they operate at different layers:

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions CI/CD (Terraform)                       │
│  Creates/manages the workspace containers, capacity,    │
│  and infrastructure resources.                          │
├─────────────────────────────────────────────────────────┤
│  Fabric Deployment Pipelines (Native)                   │
│  Promotes the content inside workspaces — lakehouse     │
│  data, semantic models, reports, notebooks — through    │
│  Dev → Test → Prod stages.                              │
└─────────────────────────────────────────────────────────┘
```

---

## When to Use Which

### Use GitHub Actions + Terraform when:

- **Creating or modifying infrastructure** — new workspaces, lakehouses, warehouses,
  eventstreams, connections, capacity changes
- **Managing notebook source code** — version-controlled `.py` files deployed via
  `fabric_notebook` Terraform resource
- **Enforcing configuration drift** — Terraform state ensures declared resources
  match actual Fabric state
- **Cross-cloud resources** — Azure Storage accounts, Key Vaults, RBAC assignments

### Use Fabric Deployment Pipelines when:

- **Promoting Fabric item content** — after a semantic model is built in Dev, promote
  it to Test/Prod without re-creating the resource
- **Promoting reports** — Power BI reports connected to semantic models should be
  promoted via Fabric pipelines to preserve data source bindings
- **Staging ML model artifacts** — promote trained models from dev workspace to
  production workspace
- **Business-user-driven promotions** — analytics leads can promote reports without
  Terraform/Git knowledge

---

## Architecture

```
GitHub repo                    Fabric Service
───────────                    ──────────────
 .github/workflows/
   terraform-plan.yml  ──────► Terraform creates:
   terraform-apply.yml           ├── contoso-ingestion-dev
                                 ├── contoso-data-engineering-dev
                                 ├── contoso-analytics-dev
                                 └── ... (all 8 workspace areas × 3 envs)

 src/notebooks/        ──────► Deployed to dev workspaces via fabric_notebook

 infra/modules/
   fabric-deployment-  ──────► Creates 4 Deployment Pipelines:
   pipeline/                     ├── Retail Data Pipeline
                                 ├── Analytics & Reporting
                                 ├── Real-Time Intelligence
                                 └── AI & Data Science

                                 Each pipeline has 3 stages:
                                   Dev ──► Test ──► Production
                                   (workspace assignments per domain)
```

---

## Step-by-Step Setup

### 1. Prerequisites

- Fabric Capacity provisioned (F8 or higher for deployment pipelines)
- Workspaces created for all three environments (dev, test, prod)
- Terraform provider `microsoft/fabric ~> 1.8` with `preview = true`

### 2. Enable Preview Mode in Provider

Deployment pipelines require preview mode. Update `providers.tf`:

```hcl
provider "fabric" {
  preview = true
}
```

### 3. Deploy Pipeline Infrastructure via Terraform

The `fabric-deployment-pipeline` module creates the pipeline and stage
definitions. Add to your environment `main.tf`:

```hcl
module "deployment_pipeline_retail" {
  source = "../../modules/fabric-deployment-pipeline"

  display_name = "Retail Data Pipeline"
  description  = "Dev → Test → Prod promotion for ingestion & data engineering"

  stages = [
    {
      display_name = "Development"
      description  = "Dev workspace — active development and testing"
      is_public    = false
      workspace_id = module.fabric_workspaces["ingestion"].workspace_id
    },
    {
      display_name = "Test"
      description  = "Test workspace — integration testing and UAT"
      is_public    = false
      workspace_id = null  # Assign after test workspace is created
    },
    {
      display_name = "Production"
      description  = "Prod workspace — live production environment"
      is_public    = false
      workspace_id = null  # Assign after prod workspace is created
    },
  ]
}
```

### 4. Assign Workspaces to Stages

After Terraform creates the pipeline, assign workspaces to Test and
Production stages:

**Option A: Terraform** — Pass workspace IDs from the test/prod environment
outputs into the stage `workspace_id` fields.

**Option B: Fabric Portal** — Navigate to *Deployment Pipelines* in the Fabric
portal, select the pipeline, and assign workspaces manually to each stage.

### 5. Configure Deployment Rules

Open `src/governance/deployment_pipeline_config.json` for the full rule
definitions. Key rules per pipeline:

| Pipeline | Semantic Models | Reports | Notebooks |
|---|---|---|---|
| Retail Data | N/A | N/A | Require test pass |
| Analytics & Reporting | Require approval + data-source rebind | Auto-deploy | N/A |
| Real-Time Intelligence | N/A | N/A | Require test pass |
| AI & Data Science | N/A | N/A | Require test pass + model accuracy check |

### 6. Integrate with GitHub Actions

Add a post-deployment step to GitHub Actions that triggers a Fabric
deployment pipeline promotion via REST API after Terraform applies:

```yaml
# .github/workflows/terraform-apply.yml (add after terraform apply step)
- name: Trigger Fabric Pipeline Promotion (Dev → Test)
  if: github.ref == 'refs/heads/main'
  run: |
    curl -X POST \
      "https://api.fabric.microsoft.com/v1/deploymentPipelines/${PIPELINE_ID}/deploy" \
      -H "Authorization: Bearer ${{ secrets.FABRIC_TOKEN }}" \
      -H "Content-Type: application/json" \
      -d '{
        "sourceStageId": "${{ env.DEV_STAGE_ID }}",
        "isBackwardDeployment": false,
        "newDeploymentNote": "Automated promotion from CI/CD run #${{ github.run_number }}"
      }'
```

---

## Deployment Pipeline Lifecycle

```
Developer pushes code
        │
        ▼
GitHub Actions: terraform plan/apply
        │ Creates/updates infrastructure
        ▼
Fabric Dev Workspace
        │ Developer iterates on content
        ▼
Fabric Deployment Pipeline: Dev → Test
        │ Manual or automated promotion
        │ (semantic models require approval)
        ▼
Fabric Test Workspace
        │ QA validates reports, data quality
        ▼
Fabric Deployment Pipeline: Test → Prod
        │ Requires approval gate
        │ (see deployment_pipeline_config.json)
        ▼
Fabric Prod Workspace
        │ Live production environment
        ▼
Monitoring & Alerting
```

---

## Troubleshooting

| Issue | Resolution |
|---|---|
| Pipeline creation fails | Ensure `preview = true` in fabric provider config |
| Workspace assignment fails | Verify workspace exists and caller has Admin role |
| Promotion fails for semantic models | Check data-source rebind rules; prod may need different connection strings |
| Reports show stale data after promotion | Refresh the semantic model in the target workspace |
| Notebooks fail after promotion | Verify lakehouse references use workspace-relative paths, not hardcoded workspace IDs |

---

## References

- [Fabric Deployment Pipelines documentation](https://learn.microsoft.com/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines)
- [Terraform `fabric_deployment_pipeline` resource](https://registry.terraform.io/providers/microsoft/fabric/latest/docs/resources/deployment_pipeline)
- [`deployment_pipeline_config.json`](./deployment_pipeline_config.json) — Full rule definitions
