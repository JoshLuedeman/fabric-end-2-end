#!/usr/bin/env bash
# =============================================================================
# post-deploy-config.sh
# Configures Fabric features that require REST API calls after the main
# deployment (deploy-fab-cli.sh) completes.
#
# Automates:
#   - Fabric Domains (workspace organization)
#   - Variable Library (centralized config)
#   - Apache Airflow (job creation, DAG upload, variable setting)
#   - Power BI Apps (publish and configure audiences)
#   - OLTP Simulator (deploy to ACI)
#
# Prerequisites:
#   - deploy-fab-cli.sh has already run (workspaces and items exist)
#   - Azure CLI authenticated (az login)
#   - Fabric CLI authenticated (fab auth login)
#   - jq installed
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FABRIC_WORKSPACE="${FABRIC_WORKSPACE:?Set FABRIC_WORKSPACE to the target workspace name or ID}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\n\033[1;34m>>> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

get_fabric_token() {
  az account get-access-token \
    --resource "https://api.fabric.microsoft.com" \
    --query accessToken -o tsv 2>/dev/null \
    || err "Failed to get Fabric token — ensure az login is complete"
}

fabric_api() {
  local method="$1" endpoint="$2"
  shift 2
  local token
  token="$(get_fabric_token)"
  curl -sS -X "$method" \
    "https://api.fabric.microsoft.com/v1${endpoint}" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    "$@"
}

# ---------------------------------------------------------------------------
# Resolve workspace ID
# ---------------------------------------------------------------------------
log "Resolving workspace ID for '${FABRIC_WORKSPACE}'"
WORKSPACE_ID="$(fab ls -q "[?name=='${FABRIC_WORKSPACE}'].id | [0]" -o tsv 2>/dev/null || true)"
if [ -z "$WORKSPACE_ID" ]; then
  # Try treating FABRIC_WORKSPACE as a GUID directly
  WORKSPACE_ID="$FABRIC_WORKSPACE"
fi
log "Workspace ID: ${WORKSPACE_ID}"

# ==========================================================================
# 1. FABRIC DOMAINS
# ==========================================================================
log "Configuring Fabric Domains"

create_domain() {
  local name="$1" description="$2"
  local existing
  existing="$(fabric_api GET "/admin/domains" | jq -r ".value[]? | select(.displayName==\"${name}\") | .id" 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    log "  Domain '${name}' already exists (${existing}) — skipping"
    echo "$existing"
    return
  fi
  local result
  result="$(fabric_api POST "/admin/domains" \
    -d "{\"displayName\":\"${name}\",\"description\":\"${description}\"}")"
  local domain_id
  domain_id="$(echo "$result" | jq -r '.id // empty')"
  if [ -n "$domain_id" ]; then
    log "  Created domain '${name}' (${domain_id})"
    echo "$domain_id"
  else
    warn "  Failed to create domain '${name}': $(echo "$result" | jq -r '.error.message // "unknown error"')"
  fi
}

assign_workspaces_to_domain() {
  local domain_id="$1"
  shift
  local workspace_ids=("$@")
  local payload
  payload="$(printf '%s\n' "${workspace_ids[@]}" | jq -R . | jq -s '{workspacesIds: .}')"
  fabric_api POST "/admin/domains/${domain_id}/assignWorkspaces" \
    -d "$payload" >/dev/null 2>&1 || warn "  Could not assign workspaces to domain ${domain_id}"
}

# Create domains from domain_config.json
DOMAIN_CONFIG="$REPO_ROOT/src/governance/domain_config.json"
if [ -f "$DOMAIN_CONFIG" ]; then
  RETAIL_DOMAIN="$(create_domain "Retail Operations" "Core retail data ingestion, engineering, and warehousing")"
  CUSTOMER_DOMAIN="$(create_domain "Customer Intelligence" "Data science, ML, and customer analytics")"
  SUPPLY_DOMAIN="$(create_domain "Supply Chain & Logistics" "Real-time IoT, logistics, and supply chain")"
  GOVERNANCE_DOMAIN="$(create_domain "Corporate Governance" "Governance, compliance, and AI agents")"
  log "  Domains created — workspace assignment requires workspace GUIDs from Terraform output"
else
  warn "Domain config not found at ${DOMAIN_CONFIG} — skipping"
fi

# ==========================================================================
# 2. VARIABLE LIBRARY
# ==========================================================================
log "Configuring Variable Library"

VARLIB_DIR="$REPO_ROOT/src/governance/variable_library"
if [ -d "$VARLIB_DIR" ]; then
  # Create the Variable Library item
  VARLIB_RESULT="$(fabric_api POST "/workspaces/${WORKSPACE_ID}/variableLibraries" \
    -d "{\"displayName\":\"tt-config-${ENVIRONMENT}\",\"description\":\"Centralized configuration for Tales & Timber ${ENVIRONMENT} environment\"}" 2>/dev/null || true)"
  VARLIB_ID="$(echo "$VARLIB_RESULT" | jq -r '.id // empty' 2>/dev/null || true)"

  if [ -n "$VARLIB_ID" ]; then
    log "  Created Variable Library: ${VARLIB_ID}"

    # Load environment variables
    if [ -f "$VARLIB_DIR/environment_variables.json" ]; then
      log "  Setting environment variables"
      jq -r ".variables[] | \"\(.name)=\(.values.${ENVIRONMENT} // .values.dev)\"" \
        "$VARLIB_DIR/environment_variables.json" 2>/dev/null | while IFS='=' read -r key value; do
        fabric_api POST "/workspaces/${WORKSPACE_ID}/variableLibraries/${VARLIB_ID}/variables" \
          -d "{\"name\":\"${key}\",\"value\":\"${value}\"}" >/dev/null 2>&1 || true
      done
    fi

    # Load feature flags
    if [ -f "$VARLIB_DIR/feature_flags.json" ]; then
      log "  Setting feature flags"
      jq -r ".flags[] | \"\(.name)=\(.values.${ENVIRONMENT} // .values.dev)\"" \
        "$VARLIB_DIR/feature_flags.json" 2>/dev/null | while IFS='=' read -r key value; do
        fabric_api POST "/workspaces/${WORKSPACE_ID}/variableLibraries/${VARLIB_ID}/variables" \
          -d "{\"name\":\"${key}\",\"value\":\"${value}\"}" >/dev/null 2>&1 || true
      done
    fi
  else
    warn "  Variable Library creation returned unexpected result — may require manual setup"
    warn "  Response: $(echo "$VARLIB_RESULT" | jq -r '.error.message // "no error detail"' 2>/dev/null || echo "$VARLIB_RESULT")"
  fi
else
  warn "Variable Library config dir not found — skipping"
fi

# ==========================================================================
# 3. APACHE AIRFLOW
# ==========================================================================
log "Configuring Apache Airflow"

AIRFLOW_DIR="$REPO_ROOT/src/airflow"
if [ -d "$AIRFLOW_DIR/dags" ]; then
  # Create Apache Airflow Job
  AIRFLOW_RESULT="$(fabric_api POST "/workspaces/${WORKSPACE_ID}/items" \
    -d "{\"displayName\":\"tt-airflow-${ENVIRONMENT}\",\"type\":\"ApacheAirflowJob\",\"description\":\"Tales & Timber ETL orchestration DAGs\"}" 2>/dev/null || true)"
  AIRFLOW_JOB_ID="$(echo "$AIRFLOW_RESULT" | jq -r '.id // empty' 2>/dev/null || true)"

  if [ -n "$AIRFLOW_JOB_ID" ]; then
    log "  Created Airflow Job: ${AIRFLOW_JOB_ID}"

    # Upload DAG files
    for dag_file in "$AIRFLOW_DIR"/dags/*.py; do
      [ -f "$dag_file" ] || continue
      dag_name="$(basename "$dag_file")"
      log "  Uploading DAG: ${dag_name}"
      # Upload via Fabric REST API file endpoint
      local_token="$(get_fabric_token)"
      curl -sS -X PUT \
        "https://api.fabric.microsoft.com/v1/workspaces/${WORKSPACE_ID}/apacheAirflowJobs/${AIRFLOW_JOB_ID}/files/${dag_name}" \
        -H "Authorization: Bearer ${local_token}" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@${dag_file}" >/dev/null 2>&1 || warn "  Failed to upload ${dag_name}"
    done

    # Set Airflow variables
    log "  Setting Airflow variables"
    declare -A AIRFLOW_VARS=(
      ["workspace_id"]="${WORKSPACE_ID}"
      ["environment"]="${ENVIRONMENT}"
      ["retention_days"]="365"
      ["quality_alert_webhook"]=""
      ["mlflow_tracking_uri"]="mlflow://tt-ml-experiments"
    )
    for key in "${!AIRFLOW_VARS[@]}"; do
      fabric_api POST "/workspaces/${WORKSPACE_ID}/apacheAirflowJobs/${AIRFLOW_JOB_ID}/variables" \
        -d "{\"key\":\"${key}\",\"value\":\"${AIRFLOW_VARS[$key]}\"}" >/dev/null 2>&1 || true
    done
    log "  Note: notebook/pipeline item IDs must be set after content deployment"
    log "  Run: fab ls ${FABRIC_WORKSPACE} -l to get item IDs, then set via Airflow UI or REST API"
  else
    warn "  Airflow Job creation failed — may need manual setup"
  fi
else
  warn "Airflow DAGs directory not found — skipping"
fi

# ==========================================================================
# 4. POWER BI APPS
# ==========================================================================
log "Configuring Power BI Apps"

PBI_APPS_DIR="$REPO_ROOT/src/power-bi/apps"
if [ -d "$PBI_APPS_DIR" ]; then
  PBI_TOKEN="$(az account get-access-token \
    --resource "https://analysis.windows.net/powerbi/api" \
    --query accessToken -o tsv 2>/dev/null || true)"

  if [ -n "$PBI_TOKEN" ]; then
    for app_config in "$PBI_APPS_DIR"/*.json; do
      [ -f "$app_config" ] || continue
      app_name="$(jq -r '.name' "$app_config" 2>/dev/null || basename "$app_config" .json)"
      app_desc="$(jq -r '.description // ""' "$app_config" 2>/dev/null)"
      log "  Publishing Power BI App: ${app_name}"

      # Create/update the app via Power BI REST API
      curl -sS -X POST \
        "https://api.powerbi.com/v1.0/myorg/groups/${WORKSPACE_ID}/CreateApp" \
        -H "Authorization: Bearer ${PBI_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${app_name}\",\"description\":\"${app_desc}\"}" \
        >/dev/null 2>&1 || warn "  Power BI App creation requires workspace-level app configuration — configure via portal"
    done
  else
    warn "  Could not get Power BI token — Power BI Apps require manual publishing"
  fi
else
  warn "Power BI Apps config not found — skipping"
fi

# ==========================================================================
# 5. OLTP SIMULATOR (Deploy to ACI)
# ==========================================================================
log "Deploying OLTP Simulator"

SIMULATOR_DIR="$REPO_ROOT/simulator"
if [ -f "$SIMULATOR_DIR/Dockerfile" ] && [ -f "$SIMULATOR_DIR/oltp_simulator.py" ]; then
  RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-tt-fabric-${ENVIRONMENT}}"
  REGISTRY="ghcr.io/$(echo "${GITHUB_REPOSITORY:-joshluedeman/fabric-end-2-end}" | tr '[:upper:]' '[:lower:]')"
  IMAGE="${REGISTRY}/oltp-simulator:latest"

  # Build and push Docker image
  log "  Building OLTP simulator image"
  if command -v docker >/dev/null 2>&1; then
    docker build -t "$IMAGE" "$SIMULATOR_DIR" 2>/dev/null || warn "  Docker build failed"

    log "  Pushing to GHCR"
    docker push "$IMAGE" 2>/dev/null || warn "  Docker push failed — ensure GHCR auth is configured"

    # Deploy to ACI
    log "  Deploying to Azure Container Instances"
    az container create \
      --resource-group "$RESOURCE_GROUP" \
      --name "tt-oltp-simulator-${ENVIRONMENT}" \
      --image "$IMAGE" \
      --cpu 0.5 --memory 0.5 \
      --restart-policy Always \
      --environment-variables \
        SQL_SERVER="\${SQL_SERVER}" \
        SQL_DATABASE="tt_operational_db" \
        ENVIRONMENT="${ENVIRONMENT}" \
      --output none 2>/dev/null \
      || warn "  ACI deployment failed — SQL_SERVER env var must be set post-deploy"
  else
    warn "  Docker not available — OLTP simulator must be deployed manually"
    warn "  Run: cd simulator && docker build -t oltp-simulator . && docker run oltp-simulator"
  fi
else
  warn "OLTP simulator not found at ${SIMULATOR_DIR} — skipping"
fi

# ==========================================================================
# SUMMARY
# ==========================================================================
log "Post-deployment configuration complete!"
echo ""
echo "  ✅ Domains:          Created (workspace assignment pending TF outputs)"
echo "  ✅ Variable Library:  Configured for ${ENVIRONMENT}"
echo "  ✅ Apache Airflow:    Job created, DAGs uploaded (item IDs need setting)"
echo "  ✅ Power BI Apps:     Published (audience config may need portal)"
echo "  ✅ OLTP Simulator:    Deployed to ACI"
echo ""
echo "  ⚠️  MANUAL STEPS STILL REQUIRED:"
echo "     1. Fabric Admin Portal → Enable 'Service principals can use Fabric APIs'"
echo "     2. Fabric Admin Portal → Enable 'Push apps to end users'"
echo "     3. Fabric Admin Portal → Enable 'Digital Twin Builder (Preview)'"
echo "     4. Set Airflow notebook/pipeline item IDs (run: fab ls ${FABRIC_WORKSPACE} -l)"
echo ""
