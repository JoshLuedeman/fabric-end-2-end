# Contoso Global Retail — Branched Workspaces Strategy

> **Status:** Planning — Branched Workspaces was announced at FabCon 2026.  
> **Applies to:** All 8 Contoso Fabric workspaces across dev and prod environments.  
> **Complements:** GitHub Actions CI/CD (`/.github/workflows/`) and native Deployment Pipelines (`src/governance/deployment_pipeline_config.json`).

---

## Table of Contents

1. [Overview](#overview)
2. [How Branched Workspaces Fit Our ALM Strategy](#how-branched-workspaces-fit-our-alm-strategy)
3. [Branch Types & Naming Conventions](#branch-types--naming-conventions)
4. [Branching Strategy by Workspace Area](#branching-strategy-by-workspace-area)
5. [Merge Rules & Approvals](#merge-rules--approvals)
6. [Isolation Levels](#isolation-levels)
7. [Relationship with Git Integration & CI/CD](#relationship-with-git-integration--cicd)
8. [Relationship with Deployment Pipelines](#relationship-with-deployment-pipelines)
9. [Lifecycle Management](#lifecycle-management)
10. [Limitations & Considerations](#limitations--considerations)

---

## Overview

Branched Workspaces allow creating isolated copies of a Fabric workspace — including its lakehouses, warehouses, semantic models, reports, notebooks, and pipelines — for development and testing. This is analogous to Git branches but operates at the **Fabric item level**, providing data isolation that Git-based source control alone cannot achieve.

### Key Capabilities

- **Full isolation:** Each workspace branch gets its own compute and data snapshot
- **Comparison view:** Side-by-side diff of items between branches before merging
- **Merge requests:** Approval-gated merge workflow with conflict detection
- **Auto-cleanup:** Branches can be automatically deleted when their purpose is fulfilled
- **Data snapshots:** Branch workspaces can snapshot table data at branch-creation time

---

## How Branched Workspaces Fit Our ALM Strategy

Contoso uses a **three-layer ALM approach**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Git Integration (GitHub)                                  │
│  ─ Source control for code artifacts: notebooks, SQL, Power Query,  │
│    semantic model definitions (.bim), report definitions (.pbip)    │
│  ─ GitHub Actions for CI/CD (lint, test, deploy)                    │
│  ─ Pull requests for code review                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Branched Workspaces (Fabric-native)                       │
│  ─ Isolated development environments for Fabric items               │
│  ─ Data snapshot isolation (branch gets copy of tables)             │
│  ─ Visual comparison & merge of non-code items (reports, dashboards)│
│  ─ Testing with real (or sampled) data in isolation                 │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: Deployment Pipelines (Fabric-native)                      │
│  ─ Promotes workspace content across environments: Dev → Test → Prod│
│  ─ Approval gates and pre-deployment checks                         │
│  ─ Automatic data source rebinding on promotion                     │
│  ─ Rollback on failure                                              │
└─────────────────────────────────────────────────────────────────────┘
```

**How they work together:**

1. Developer creates a **Git branch** + a **workspace branch** simultaneously
2. Code changes (notebooks, SQL) are committed to the Git branch
3. Fabric item changes (report layouts, semantic model tweaks) exist in the workspace branch
4. Both are reviewed: Git PR for code, workspace merge request for items
5. After merge, the **Deployment Pipeline** promotes the result from Dev → Test → Prod

---

## Branch Types & Naming Conventions

| Branch Type | Naming Convention | Purpose | Lifetime |
|---|---|---|---|
| **Main** | `main` | Production-ready workspace state; always stable | Permanent |
| **Feature** | `feature/<ticket-id>-<short-description>` | Isolated development for a new feature or enhancement | Until merged or abandoned (max 30 days) |
| **Release** | `release/v<semver>` (e.g., `release/v2.4.0`) | Staging for pre-production validation and regression testing | Until deployed to prod (typically 1–5 days) |
| **Hotfix** | `hotfix/<short-description>` | Emergency production fix, branched from `main` | Until merged (max 48 hours) |
| **Experiment** | `experiment/<description>` | Exploratory work for spikes; never merged to main directly | Max 14 days, then document findings and delete |

### Naming Examples

```
feature/CONTOSO-1234-add-customer-churn-model
feature/CONTOSO-5678-update-inventory-dashboard
release/v2.4.0
hotfix/fix-rls-filter-missing-region
experiment/test-direct-lake-performance
```

---

## Branching Strategy by Workspace Area

Not all workspaces benefit equally from branching. Here's our guidance:

| Workspace | Branch Strategy | Rationale |
|---|---|---|
| **analytics** | ✅ Heavy use | Reports, semantic models, and scorecards change frequently; need isolation for visual QA |
| **data-warehouse** | ✅ Heavy use | Schema changes (new columns, views) need isolated testing with data snapshots |
| **data-engineering** | ✅ Moderate use | Notebook and pipeline changes need testing against bronze/silver/gold data |
| **data-science** | ✅ Moderate use | ML model experiments benefit from isolated runs with consistent data |
| **real-time** | ⚠️ Light use | Eventstreams are harder to branch; use for KQL query/Reflex changes only |
| **ingestion** | ⚠️ Light use | Copy jobs and mirrors are environment-specific; branch for connection config changes |
| **governance** | ❌ Rarely | Governance items (domains, deployment pipelines) are cross-workspace; modify directly |
| **ai-agents** | ⚠️ Light use | Agent config changes can be branched for prompt/data source testing |

---

## Merge Rules & Approvals

### Feature Branch → Main

| Criterion | Requirement |
|---|---|
| Approvals required | **1 approval** from a workspace Contributor or Admin |
| Automated checks | All data pipeline runs in branch succeeded (last 24 hours) |
| Data quality | Great Expectations validation suite passed |
| Schema compatibility | No breaking changes detected (dropped columns, renamed tables) |
| Report validation | All report pages render without errors |
| Semantic model | No broken relationships or orphaned measures |
| Git sync | Corresponding Git PR must be merged first (if applicable) |

### Release Branch → Main

| Criterion | Requirement |
|---|---|
| Approvals required | **2 approvals** (engineering lead + QA lead) |
| Regression tests | Full regression suite passed in the release branch workspace |
| Performance | Query response times within SLA (p95 < 5s for dashboard queries) |
| Sign-off | Product Owner sign-off on feature completeness |

### Hotfix Branch → Main

| Criterion | Requirement |
|---|---|
| Approvals required | **1 approval** from an engineering lead or on-call engineer |
| Scope | Changes limited to the specific fix (no bundled features) |
| Rollback plan | Documented rollback procedure attached to the merge request |
| Time limit | Must be merged within 48 hours of creation |

---

## Isolation Levels

Branched workspaces support two isolation levels:

### Full Isolation (Recommended for Data-Intensive Branches)

- **Separate compute:** Branch workspace gets its own SQL/Spark endpoints
- **Data snapshot:** Tables are copied at branch-creation time (point-in-time snapshot)
- **Cost:** Higher — consumes capacity for the branch's compute and storage
- **Use when:** Testing schema changes, running ETL pipelines, validating data transformations

### Shared Isolation (Recommended for Report/UI Branches)

- **Shared compute:** Branch reads from the same underlying data as main
- **No data copy:** Reports query the live main data
- **Cost:** Lower — only metadata and report definitions are duplicated
- **Use when:** Updating report layouts, adding new visuals, tweaking DAX measures

### Contoso Default by Workspace

| Workspace | Default Isolation |
|---|---|
| analytics | Shared |
| data-warehouse | Full |
| data-engineering | Full |
| data-science | Full |
| real-time | Shared |
| ingestion | Full |
| ai-agents | Shared |

---

## Relationship with Git Integration & CI/CD

Branched Workspaces and Git integration serve **complementary** purposes:

| Concern | Git Integration | Branched Workspaces |
|---|---|---|
| **What it tracks** | Code-as-text (notebooks, SQL, .bim, .pbip) | Fabric items (runtime state, data, compute) |
| **Isolation** | Code only (no data, no compute) | Code + data + compute |
| **Diffing** | Text-based diff | Visual comparison (side-by-side report preview) |
| **Merge** | Git merge (3-way text merge) | Fabric merge (item-level replacement or conflict resolution) |
| **CI/CD** | GitHub Actions runs tests on code | Workspace branch runs validate with real data |

### Recommended Workflow

```
1. Create Git branch:          git checkout -b feature/CONTOSO-1234-churn-model
2. Create workspace branch:    Fabric Portal → Workspace → Branch → New from main
                               Name: feature/CONTOSO-1234-churn-model
3. Develop:
   - Code changes → commit to Git branch
   - Item changes → saved in workspace branch automatically
4. Test:
   - GitHub Actions runs unit tests on Git branch
   - Workspace branch runs integration tests with isolated data
5. Review:
   - Open Git PR → code review by peers
   - Open workspace merge request → visual QA by stakeholders
6. Merge:
   - Merge Git PR first (code is source of truth)
   - Then merge workspace branch (reconciles Fabric items)
7. Deploy:
   - Deployment Pipeline promotes main workspace: Dev → Test → Prod
```

---

## Relationship with Deployment Pipelines

Deployment Pipelines and Branched Workspaces operate at different scopes:

- **Branched Workspaces:** Horizontal branching within a single environment (e.g., dev workspace → dev feature branch)
- **Deployment Pipelines:** Vertical promotion across environments (dev → test → prod)

```
                    ┌─────────────────────┐
                    │  feature/CONTOSO-1234│ ◄── Workspace branch (dev)
                    └──────────┬──────────┘
                               │ merge
                    ┌──────────▼──────────┐
                    │     main (dev)       │ ◄── Dev workspace
                    └──────────┬──────────┘
                               │ Deployment Pipeline: Dev → Test
                    ┌──────────▼──────────┐
                    │     main (test)      │ ◄── Test workspace
                    └──────────┬──────────┘
                               │ Deployment Pipeline: Test → Prod (approval required)
                    ┌──────────▼──────────┐
                    │     main (prod)      │ ◄── Production workspace
                    └─────────────────────┘
```

**Rule:** Branches are only created in the **Dev** environment. Test and Prod never have branches — they receive content only through Deployment Pipelines.

---

## Lifecycle Management

### Auto-Creation

When a GitHub PR is opened targeting `main`:
1. GitHub Actions detects the PR event
2. A webhook calls the Fabric REST API to create a workspace branch matching the Git branch name
3. The workspace branch is tagged with the PR number for tracking

### Auto-Cleanup

| Trigger | Action |
|---|---|
| Git PR merged | Workspace branch merged (if not already) and deleted |
| Git PR closed (not merged) | Workspace branch deleted after 24-hour grace period |
| Branch age > 30 days | Alert sent to branch creator; auto-delete after 7 days if no activity |
| Experiment branch > 14 days | Auto-deleted; findings must be documented before expiry |

### Cost Controls

- Maximum concurrent branches per workspace: **5** (prevents capacity overuse)
- Full-isolation branches consume capacity — monitor via Azure Cost Management
- Idle branches (no activity for 7+ days) are flagged for review
- Branch compute is suspended after 2 hours of inactivity (resumes on next access)

---

## Limitations & Considerations

1. **Preview feature:** Branched Workspaces was announced at FabCon 2026 and may have limited availability. Check [Microsoft Fabric release notes](https://learn.microsoft.com/fabric/release-plan/) for GA status.

2. **No Terraform support yet:** As of provider `microsoft/fabric ~> 1.8`, there is no `fabric_workspace_branch` resource. Branch management is done via:
   - Fabric Portal (manual)
   - Fabric REST API (`POST /v1/workspaces/{id}/branches`)
   - GitHub Actions automation (see `.github/workflows/`)

3. **Data snapshot costs:** Full-isolation branches copy table data, which consumes OneLake storage. Budget for 10–20% additional storage for active feature branches.

4. **Eventstream branching:** Real-time eventstreams cannot be fully branched. The workspace branch will reference the same event hub; use a separate test event hub for isolation.

5. **Cross-workspace dependencies:** If a report in the `analytics` workspace references a semantic model in `data-warehouse`, both workspaces need corresponding branches for full isolation.

6. **Merge conflicts:** Schema-level conflicts (e.g., two branches modify the same warehouse table) require manual resolution. Report-level conflicts use last-writer-wins by default.
