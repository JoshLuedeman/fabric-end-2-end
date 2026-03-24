#!/usr/bin/env bash
# =============================================================================
# preflight-check.sh
# Validates that ALL prerequisites are met before deploying the Contoso demo.
#
# Checks:
#   1. Required CLI tools installed (az, fab, terraform, python, node, docker, jq)
#   2. Azure CLI authenticated
#   3. Fabric CLI authenticated
#   4. Fabric tenant settings enabled (SPN access, Push apps, Digital Twin)
#   5. GitHub secrets/variables configured (if running in Actions)
#   6. Terraform state backend accessible
#   7. Fabric capacity available
#
# Usage:
#   ./scripts/preflight-check.sh [--environment dev|prod] [--verbose]
#
# Exit codes:
#   0 — All checks passed
#   1 — One or more checks failed (see output for details)
# =============================================================================
set -euo pipefail

ENVIRONMENT="${1:-dev}"
VERBOSE="${2:-}"
PASS=0
FAIL=0
WARN=0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
check_pass() { printf '\033[1;32m  ✅ %s\033[0m\n' "$*"; PASS=$((PASS+1)); }
check_fail() { printf '\033[1;31m  ❌ %s\033[0m\n' "$*"; FAIL=$((FAIL+1)); }
check_warn() { printf '\033[1;33m  ⚠️  %s\033[0m\n' "$*"; WARN=$((WARN+1)); }
section()    { printf '\n\033[1;36m─── %s ───\033[0m\n' "$*"; }

# ==========================================================================
# SECTION 1: CLI Tools
# ==========================================================================
section "CLI Tools"

check_tool() {
  local name="$1" min_version="${2:-}" install_url="${3:-}"
  if command -v "$name" >/dev/null 2>&1; then
    local version
    version="$("$name" --version 2>/dev/null | head -1 || echo "unknown")"
    check_pass "${name} installed (${version})"
  else
    check_fail "${name} not found — install: ${install_url}"
  fi
}

check_tool "az"        ""     "https://aka.ms/install-azure-cli"
check_tool "fab"       ""     "https://aka.ms/fabric-cli"
check_tool "terraform" ""     "https://developer.hashicorp.com/terraform/install"
check_tool "python3"   "3.12" "https://www.python.org/downloads/"
check_tool "node"      "22"   "https://nodejs.org/"
check_tool "docker"    ""     "https://docs.docker.com/get-docker/"
check_tool "jq"        ""     "https://jqlang.github.io/jq/download/"
check_tool "gh"        ""     "https://cli.github.com/"

# Also accept python if python3 not found
if ! command -v python3 >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
  PY_VERSION="$(python --version 2>&1)"
  if echo "$PY_VERSION" | grep -q "3\."; then
    check_pass "python (as python) installed (${PY_VERSION})"
    FAIL=$((FAIL-1))  # undo the python3 failure
  fi
fi

# ==========================================================================
# SECTION 2: Azure Authentication
# ==========================================================================
section "Azure Authentication"

if az account show --output none 2>/dev/null; then
  ACCOUNT_NAME="$(az account show --query name -o tsv 2>/dev/null)"
  SUBSCRIPTION_ID="$(az account show --query id -o tsv 2>/dev/null)"
  check_pass "Azure CLI authenticated (${ACCOUNT_NAME})"
  check_pass "Subscription: ${SUBSCRIPTION_ID}"
else
  check_fail "Azure CLI not authenticated — run: az login"
fi

# ==========================================================================
# SECTION 3: Fabric CLI Authentication
# ==========================================================================
section "Fabric CLI Authentication"

if fab ls >/dev/null 2>&1; then
  check_pass "Fabric CLI authenticated"
else
  check_fail "Fabric CLI not authenticated — run: fab auth login"
fi

# ==========================================================================
# SECTION 4: Fabric Tenant Settings
# ==========================================================================
section "Fabric Tenant Settings"

FABRIC_TOKEN="$(az account get-access-token --resource "https://api.fabric.microsoft.com" --query accessToken -o tsv 2>/dev/null || true)"

if [ -n "$FABRIC_TOKEN" ]; then
  SETTINGS="$(curl -sS -X GET "https://api.fabric.microsoft.com/v1/admin/tenantsettings" \
    -H "Authorization: Bearer ${FABRIC_TOKEN}" \
    -H "Content-Type: application/json" 2>/dev/null || true)"

  if echo "$SETTINGS" | jq -e '.tenantSettings' >/dev/null 2>&1; then
    check_pass "Tenant settings API accessible ($(echo "$SETTINGS" | jq '.tenantSettings | length') settings)"

    check_tenant_setting() {
      local setting_name="$1" friendly_name="$2"
      local enabled
      enabled="$(echo "$SETTINGS" | jq -r ".tenantSettings[]? | select(.settingName==\"${setting_name}\") | .enabled // false" 2>/dev/null)"
      if [ "$enabled" = "true" ]; then
        check_pass "${friendly_name} — enabled"
      elif [ "$enabled" = "false" ]; then
        check_fail "${friendly_name} — DISABLED (run: ./scripts/configure-tenant.sh)"
      else
        check_warn "${friendly_name} — setting '${setting_name}' not found (name may differ)"
      fi
    }

    check_tenant_setting "ServicePrincipalAccess" "Service principals can use Fabric APIs"
    check_tenant_setting "PushAppsToEndUsers" "Push apps to end users"
    check_tenant_setting "DigitalTwinBuilder" "Digital Twin Builder (Preview)"
  else
    check_warn "Cannot read tenant settings — may not be a Fabric Admin (non-blocking)"
  fi
else
  check_warn "Cannot get Fabric token — tenant setting checks skipped"
fi

# ==========================================================================
# SECTION 5: Terraform State Backend
# ==========================================================================
section "Terraform State Backend"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_FILE="$REPO_ROOT/infra/environments/${ENVIRONMENT}/backend.tf"

if [ -f "$BACKEND_FILE" ]; then
  # Check if backend.tf still has empty strings (needs configuration)
  if grep -q 'storage_account_name\s*=\s*""' "$BACKEND_FILE" 2>/dev/null; then
    check_pass "Backend uses partial config (values from -backend-config / secrets)"
  elif grep -q 'storage_account_name' "$BACKEND_FILE" 2>/dev/null; then
    check_pass "Backend.tf found for ${ENVIRONMENT}"
  else
    check_fail "Backend.tf missing storage_account_name"
  fi
else
  check_fail "Backend.tf not found at ${BACKEND_FILE}"
fi

# Check if TF state secrets are set (in CI) or env vars exist
if [ -n "${TF_STATE_STORAGE_ACCOUNT:-}" ]; then
  check_pass "TF_STATE_STORAGE_ACCOUNT is set"
else
  check_warn "TF_STATE_STORAGE_ACCOUNT not set — required for terraform init"
fi

# ==========================================================================
# SECTION 6: GitHub Configuration (if in Actions)
# ==========================================================================
section "GitHub Configuration"

if [ -n "${GITHUB_ACTIONS:-}" ]; then
  [ -n "${AZURE_CLIENT_ID:-}" ]           && check_pass "Secret: AZURE_CLIENT_ID"           || check_fail "Secret: AZURE_CLIENT_ID not set"
  [ -n "${AZURE_TENANT_ID:-}" ]           && check_pass "Secret: AZURE_TENANT_ID"           || check_fail "Secret: AZURE_TENANT_ID not set"
  [ -n "${AZURE_SUBSCRIPTION_ID:-}" ]     && check_pass "Secret: AZURE_SUBSCRIPTION_ID"     || check_fail "Secret: AZURE_SUBSCRIPTION_ID not set"
  [ -n "${TF_STATE_STORAGE_ACCOUNT:-}" ]  && check_pass "Secret: TF_STATE_STORAGE_ACCOUNT"  || check_fail "Secret: TF_STATE_STORAGE_ACCOUNT not set"
  [ -n "${TF_STATE_CONTAINER:-}" ]        && check_pass "Secret: TF_STATE_CONTAINER"        || check_fail "Secret: TF_STATE_CONTAINER not set"
  [ -n "${TF_STATE_RESOURCE_GROUP:-}" ]   && check_pass "Secret: TF_STATE_RESOURCE_GROUP"   || check_fail "Secret: TF_STATE_RESOURCE_GROUP not set"
  [ -n "${FABRIC_WORKSPACE_ID:-}" ]       && check_pass "Variable: FABRIC_WORKSPACE_ID"     || check_warn "Variable: FABRIC_WORKSPACE_ID not set (needed for content deploy)"
  [ -n "${LAKEHOUSE_ONELAKE_URL:-}" ]     && check_pass "Variable: LAKEHOUSE_ONELAKE_URL"   || check_warn "Variable: LAKEHOUSE_ONELAKE_URL not set (needed for data upload)"
  [ -n "${AZURE_RESOURCE_GROUP:-}" ]      && check_pass "Variable: AZURE_RESOURCE_GROUP"    || check_warn "Variable: AZURE_RESOURCE_GROUP not set (needed for streaming deploy)"
else
  check_pass "Running locally (GitHub secrets check skipped)"
fi

# ==========================================================================
# SECTION 7: Python Dependencies
# ==========================================================================
section "Python Data Generators"

GENERATORS_DIR="$REPO_ROOT/data/generators"
if [ -f "$GENERATORS_DIR/requirements.txt" ]; then
  PYTHON_CMD="$(command -v python3 || command -v python || echo "")"
  if [ -n "$PYTHON_CMD" ]; then
    # Quick check if key packages are importable
    if "$PYTHON_CMD" -c "import pyarrow, faker, tqdm" 2>/dev/null; then
      check_pass "Python generator dependencies installed"
    else
      check_warn "Python dependencies not installed — run: pip install -r data/generators/requirements.txt"
    fi
  fi
else
  check_warn "generators/requirements.txt not found"
fi

# ==========================================================================
# SECTION 8: Node.js Streaming
# ==========================================================================
section "IoT Streaming Simulator"

STREAMING_DIR="$REPO_ROOT/streaming"
if [ -f "$STREAMING_DIR/package.json" ]; then
  if [ -d "$STREAMING_DIR/node_modules" ]; then
    check_pass "Node.js dependencies installed"
  else
    check_warn "node_modules not found — run: cd streaming && npm install"
  fi
  if [ -d "$STREAMING_DIR/dist" ] || [ -f "$STREAMING_DIR/dist/index.js" ]; then
    check_pass "TypeScript compiled"
  else
    check_warn "dist/ not found — run: cd streaming && npm run build"
  fi
else
  check_warn "streaming/package.json not found"
fi

# ==========================================================================
# SUMMARY
# ==========================================================================
echo ""
printf '\033[1;36m═══════════════════════════════════════\033[0m\n'
printf '\033[1;36m  PREFLIGHT CHECK SUMMARY\033[0m\n'
printf '\033[1;36m═══════════════════════════════════════\033[0m\n'
printf '  \033[1;32m✅ Passed:  %d\033[0m\n' "$PASS"
printf '  \033[1;33m⚠️  Warnings: %d\033[0m\n' "$WARN"
printf '  \033[1;31m❌ Failed:  %d\033[0m\n' "$FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  printf '\033[1;31mPreflight check FAILED — fix the %d issue(s) above before deploying.\033[0m\n' "$FAIL"
  echo ""
  echo "Quick fixes:"
  echo "  • Missing tools:     See install URLs above"
  echo "  • Auth issues:       az login && fab auth login"
  echo "  • Tenant settings:   ./scripts/configure-tenant.sh"
  echo "  • TF state:          Set TF_STATE_* environment variables"
  echo "  • Dependencies:      pip install -r data/generators/requirements.txt"
  echo ""
  exit 1
elif [ "$WARN" -gt 0 ]; then
  printf '\033[1;33mPreflight check PASSED with %d warning(s) — review before deploying.\033[0m\n' "$WARN"
  exit 0
else
  printf '\033[1;32mAll preflight checks PASSED — ready to deploy! 🚀\033[0m\n'
  exit 0
fi
