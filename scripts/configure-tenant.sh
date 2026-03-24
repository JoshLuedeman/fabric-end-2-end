#!/usr/bin/env bash
# =============================================================================
# configure-tenant.sh
# Configures required Fabric tenant settings via the Admin REST API (Preview).
#
# This script enables the tenant-level toggles needed for the Contoso demo
# environment to function. Must be run by a Fabric Administrator.
#
# Settings enabled:
#   1. Service principals can use Fabric APIs
#   2. Push apps to end users
#   3. Digital Twin Builder (Preview)
#   4. Users can create Fabric items
#   5. Allow XMLA endpoints
#
# Prerequisites:
#   - Azure CLI authenticated as a Fabric Administrator (az login)
#   - The authenticated identity must have Tenant.ReadWrite.All permission
#
# Usage:
#   ./scripts/configure-tenant.sh [--dry-run] [--security-group <group-id>]
#
# Options:
#   --dry-run            Show what would be changed without making changes
#   --security-group ID  Scope SPN access to a specific Entra ID security group
#                        (recommended for production — limits which SPNs can call APIs)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
DRY_RUN=false
SECURITY_GROUP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=true; shift ;;
    --security-group) SECURITY_GROUP="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--security-group <group-id>]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\033[1;34m>>> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✅ %s\033[0m\n' "$*"; }
skip() { printf '\033[1;33m  ⏭️  %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ⚠️  %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

get_fabric_token() {
  az account get-access-token \
    --resource "https://api.fabric.microsoft.com" \
    --query accessToken -o tsv 2>/dev/null \
    || err "Failed to get Fabric token — ensure 'az login' is complete and you are a Fabric Admin"
}

FABRIC_API="https://api.fabric.microsoft.com/v1"

fabric_admin_get() {
  local endpoint="$1"
  local token
  token="$(get_fabric_token)"
  curl -sS -X GET "${FABRIC_API}${endpoint}" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json"
}

fabric_admin_post() {
  local endpoint="$1" body="$2"
  local token
  token="$(get_fabric_token)"
  curl -sS -X POST "${FABRIC_API}${endpoint}" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "$body"
}

# ---------------------------------------------------------------------------
# Step 1 — Verify admin access
# ---------------------------------------------------------------------------
log "Verifying Fabric Admin access"
SETTINGS_RESPONSE="$(fabric_admin_get "/admin/tenantsettings")"
if echo "$SETTINGS_RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  ERROR_MSG="$(echo "$SETTINGS_RESPONSE" | jq -r '.error.message // "Access denied"')"
  err "Cannot read tenant settings: ${ERROR_MSG}. Ensure you are a Fabric Administrator."
fi

TOTAL_SETTINGS="$(echo "$SETTINGS_RESPONSE" | jq '.tenantSettings | length')"
log "Found ${TOTAL_SETTINGS} tenant settings"

# ---------------------------------------------------------------------------
# Helper — check if a setting is already enabled
# ---------------------------------------------------------------------------
is_setting_enabled() {
  local setting_name="$1"
  echo "$SETTINGS_RESPONSE" | jq -r \
    ".tenantSettings[]? | select(.settingName==\"${setting_name}\") | .enabled // false" 2>/dev/null
}

get_setting_title() {
  local setting_name="$1"
  echo "$SETTINGS_RESPONSE" | jq -r \
    ".tenantSettings[]? | select(.settingName==\"${setting_name}\") | .title // \"${setting_name}\"" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Helper — enable a tenant setting
# ---------------------------------------------------------------------------
enable_setting() {
  local setting_name="$1"
  local title
  title="$(get_setting_title "$setting_name")"

  local current_state
  current_state="$(is_setting_enabled "$setting_name")"

  if [ "$current_state" = "true" ]; then
    ok "${title} — already enabled"
    return 0
  fi

  if [ "$DRY_RUN" = "true" ]; then
    skip "${title} — would enable (dry-run)"
    return 0
  fi

  # Build the request body
  local body
  if [ -n "$SECURITY_GROUP" ]; then
    body="$(cat <<EOF
{
  "enabled": true,
  "enabledSecurityGroups": [
    {"graphId": "${SECURITY_GROUP}"}
  ]
}
EOF
)"
  else
    body='{"enabled": true}'
  fi

  local result
  result="$(fabric_admin_post "/admin/tenantsettings/${setting_name}/update" "$body" 2>&1)"

  if echo "$result" | jq -e '.error' >/dev/null 2>&1; then
    local error_msg
    error_msg="$(echo "$result" | jq -r '.error.message // "Unknown error"')"
    warn "${title} — failed to enable: ${error_msg}"
    return 1
  else
    ok "${title} — enabled"
    return 0
  fi
}

# ---------------------------------------------------------------------------
# Step 2 — Enable required tenant settings
# ---------------------------------------------------------------------------
echo ""
log "Configuring required tenant settings for Contoso demo environment"
echo ""

FAILED=0

# Setting 1: Service principals can use Fabric APIs
# Internal name varies — try known variants
log "[1/5] Service Principal API Access"
enable_setting "ServicePrincipalAccess" || \
  enable_setting "ServicePrincipalsCanUseAPIs" || \
  enable_setting "AllowServicePrincipalsUseRESTAPIs" || \
  { warn "Could not find/enable SPN API setting — try enabling manually in Admin Portal → Tenant settings → Developer settings"; FAILED=$((FAILED+1)); }

# Setting 2: Push apps to end users
log "[2/5] Push Apps to End Users"
enable_setting "PushAppsToEndUsers" || \
  enable_setting "InstallAppsAutomatically" || \
  { warn "Could not find/enable Push Apps setting — try Admin Portal → Tenant settings → Content pack and app settings"; FAILED=$((FAILED+1)); }

# Setting 3: Digital Twin Builder (Preview)
log "[3/5] Digital Twin Builder Preview"
enable_setting "DigitalTwinBuilder" || \
  enable_setting "DigitalTwinBuilderPreview" || \
  { warn "Could not find/enable Digital Twin Builder — try Admin Portal → Tenant settings → Preview features"; FAILED=$((FAILED+1)); }

# Setting 4: Users can create Fabric items
log "[4/5] Users Can Create Fabric Items"
enable_setting "CreateFabricItems" || \
  enable_setting "UsersCanCreateFabricItems" || \
  { skip "Create Fabric Items setting not found — likely enabled by default"; }

# Setting 5: Allow XMLA endpoints (for semantic model refresh)
log "[5/5] XMLA Endpoints"
enable_setting "AllowXMLAEndpoints" || \
  enable_setting "XMLAEndpoints" || \
  { skip "XMLA Endpoints setting not found — may be capacity-level"; }

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$DRY_RUN" = "true" ]; then
  log "Dry run complete — no changes made"
elif [ "$FAILED" -gt 0 ]; then
  warn "${FAILED} setting(s) could not be enabled automatically"
  warn "The Update Tenant Settings API is in Preview — some settings may require manual portal configuration"
  echo ""
  echo "  Manual fallback:"
  echo "    1. Go to https://app.fabric.microsoft.com/admin-portal/tenantSettings"
  echo "    2. Search for and enable the failed settings listed above"
  echo ""
else
  log "All tenant settings configured successfully!"
fi
