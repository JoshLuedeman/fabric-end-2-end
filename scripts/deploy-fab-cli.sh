#!/usr/bin/env bash
# =============================================================================
# deploy-fab-cli.sh
# Deploys the Contoso Global Retail & Supply Chain demo to Microsoft Fabric
# using the Fabric CLI (fab).
#
# FabCon / SQLCon 2026 — demonstrates automated deployment of:
#   - Lakehouses, Warehouses, Notebooks
#   - Semantic models (Direct Lake)
#   - Data Agents (AI Agents)
#   - User Data Functions (Translytical Task Flows)
#
# Prerequisites:
#   - Fabric CLI installed: https://aka.ms/fabric-cli
#   - Azure CLI authenticated (az login) or SPN credentials set
#   - Environment variables (see below) configured
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via environment variables or a .env file
# ---------------------------------------------------------------------------
FABRIC_WORKSPACE="${FABRIC_WORKSPACE:?Set FABRIC_WORKSPACE to the target workspace name or ID}"
FABRIC_CAPACITY="${FABRIC_CAPACITY:-}"                      # optional; only needed when creating a new workspace
TENANT_ID="${TENANT_ID:?Set TENANT_ID for SPN auth}"
CLIENT_ID="${CLIENT_ID:?Set CLIENT_ID for SPN auth}"
CLIENT_SECRET="${CLIENT_SECRET:-}"                          # optional fallback (deprecated — prefer OIDC or interactive login)

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\n\033[1;34m>>> %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || err "'$1' is required but not found in PATH."
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "Running pre-flight checks"
require_cmd fab
require_cmd az
require_cmd jq

# ---------------------------------------------------------------------------
# Step 1 — Authenticate (OIDC → CLIENT_SECRET fallback → interactive)
# ---------------------------------------------------------------------------
if az account show --output none 2>/dev/null; then
  log "Already authenticated with Azure CLI"
elif [ -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ]; then
  # CI/CD: Use OIDC federated credentials (GitHub Actions, Azure DevOps, etc.)
  log "Authenticating via OIDC federated token (CI/CD)"
  az login --service-principal \
    --tenant  "$TENANT_ID" \
    --username "$CLIENT_ID" \
    --federated-token "$(curl -sS -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
      "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=api://AzureADTokenExchange" | jq -r '.value')" \
    --output none
elif [ -n "${CLIENT_SECRET}" ]; then
  # Deprecated fallback — prefer OIDC or interactive login
  log "WARNING: CLIENT_SECRET auth is deprecated — migrate to OIDC federated credentials"
  az login --service-principal \
    --tenant  "$TENANT_ID" \
    --username "$CLIENT_ID" \
    --password "$CLIENT_SECRET" \
    --output none
else
  # Local development: interactive login
  log "No CI/CD token or CLIENT_SECRET found — falling back to interactive login"
  az login --use-device-code --output none
fi

fab auth login --tenant-id "$TENANT_ID" --output none

# ---------------------------------------------------------------------------
# Step 2 — Ensure workspace exists
# ---------------------------------------------------------------------------
log "Ensuring workspace '${FABRIC_WORKSPACE}' exists"
if ! fab workspace show --name "$FABRIC_WORKSPACE" >/dev/null 2>&1; then
  log "Creating workspace '${FABRIC_WORKSPACE}'"
  fab workspace create \
    --name "$FABRIC_WORKSPACE" \
    ${FABRIC_CAPACITY:+--capacity "$FABRIC_CAPACITY"}
fi

# ---------------------------------------------------------------------------
# Step 3 — Deploy Lakehouse items
# ---------------------------------------------------------------------------
log "Deploying Lakehouse items"
for lakehouse in bronze_lakehouse silver_lakehouse gold_lakehouse; do
  if ! fab item show --workspace "$FABRIC_WORKSPACE" --name "$lakehouse" --type Lakehouse >/dev/null 2>&1; then
    fab item create \
      --workspace "$FABRIC_WORKSPACE" \
      --name "$lakehouse" \
      --type Lakehouse
  else
    log "  Lakehouse '${lakehouse}' already exists — skipping"
  fi
done

# ---------------------------------------------------------------------------
# Step 4 — Deploy Warehouse
# ---------------------------------------------------------------------------
log "Deploying Warehouse"
if ! fab item show --workspace "$FABRIC_WORKSPACE" --name "contoso_warehouse" --type Warehouse >/dev/null 2>&1; then
  fab item create \
    --workspace "$FABRIC_WORKSPACE" \
    --name "contoso_warehouse" \
    --type Warehouse
fi

# ---------------------------------------------------------------------------
# Step 5 — Upload Notebooks
# ---------------------------------------------------------------------------
log "Uploading Notebooks"
for notebook_dir in "$REPO_ROOT"/src/notebooks/*/; do
  notebook_name="$(basename "$notebook_dir")"
  log "  Uploading notebook: ${notebook_name}"
  fab item create-or-update \
    --workspace "$FABRIC_WORKSPACE" \
    --name "$notebook_name" \
    --type Notebook \
    --path "$notebook_dir"
done

# ---------------------------------------------------------------------------
# Step 6 — Deploy Semantic Models (BIM files)
# ---------------------------------------------------------------------------
log "Deploying Semantic Models"
for bim_file in "$REPO_ROOT"/src/power-bi/semantic-models/*.bim; do
  model_name="$(basename "$bim_file" .bim)"
  log "  Deploying semantic model: ${model_name}"
  fab item create-or-update \
    --workspace "$FABRIC_WORKSPACE" \
    --name "$model_name" \
    --type SemanticModel \
    --path "$bim_file"
done

# ---------------------------------------------------------------------------
# Step 7 — Deploy AI Agents (FabCon 2026)
# ---------------------------------------------------------------------------
log "Deploying AI Data Agents"
for agent_dir in "$REPO_ROOT"/src/ai-agents/*/; do
  agent_name="$(basename "$agent_dir")"
  log "  Deploying agent: ${agent_name}"
  fab item create-or-update \
    --workspace "$FABRIC_WORKSPACE" \
    --name "$agent_name" \
    --type DataAgent \
    --path "$agent_dir"
done

# ---------------------------------------------------------------------------
# Step 8 — Deploy User Data Functions (FabCon 2026)
# ---------------------------------------------------------------------------
log "Deploying User Data Functions"
for fn_dir in "$REPO_ROOT"/src/user-data-functions/*/; do
  fn_name="$(basename "$fn_dir")"
  log "  Deploying function: ${fn_name}"
  fab item create-or-update \
    --workspace "$FABRIC_WORKSPACE" \
    --name "$fn_name" \
    --type UserDataFunction \
    --path "$fn_dir"
done

# ---------------------------------------------------------------------------
# Step 9 — Deploy Pipelines
# ---------------------------------------------------------------------------
log "Deploying Data Pipelines"
for pipeline_file in "$REPO_ROOT"/src/pipelines/*.json; do
  pipeline_name="$(basename "$pipeline_file" .json)"
  log "  Deploying pipeline: ${pipeline_name}"
  fab item create-or-update \
    --workspace "$FABRIC_WORKSPACE" \
    --name "$pipeline_name" \
    --type DataPipeline \
    --path "$pipeline_file"
done

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Deployment complete!"
log "Workspace: ${FABRIC_WORKSPACE}"
log "Items deployed: Lakehouses, Warehouse, Notebooks, Semantic Models, AI Agents, User Data Functions, Pipelines"
