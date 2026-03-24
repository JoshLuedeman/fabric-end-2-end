#!/usr/bin/env bash
set -euo pipefail

# Bootstrap: Create service principal and configure permissions for Fabric automation
# Usage: ./scripts/bootstrap.sh
#
# Prerequisites:
#   - Azure CLI authenticated with Owner/Global Admin permissions
#   - Fabric capacity already provisioned (or will be provisioned via Terraform)

echo "=== Fabric E2E Demo Bootstrap ==="
echo ""
echo "This script helps you set up the service principal and permissions"
echo "required for automated Fabric deployments."
echo ""

# Check prerequisites
command -v az >/dev/null 2>&1 || { echo "Error: Azure CLI (az) not found. Install from https://aka.ms/install-azure-cli"; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "Warning: GitHub CLI (gh) not found. You'll need to configure secrets manually."; }

# Get current subscription info
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Subscription: ${SUBSCRIPTION_ID}"
echo "Tenant: ${TENANT_ID}"
echo ""

# Create Azure AD App Registration
APP_NAME="fabric-e2e-demo-automation"
echo "Creating App Registration: ${APP_NAME}..."
APP_ID=$(az ad app create --display-name "${APP_NAME}" --query appId -o tsv)
echo "App ID: ${APP_ID}"

# Create Service Principal
echo "Creating Service Principal..."
SP_ID=$(az ad sp create --id "${APP_ID}" --query id -o tsv)
echo "SP Object ID: ${SP_ID}"

# Add Fabric API permissions
echo "Adding Fabric API permissions..."
# Microsoft Fabric API: Workspace.ReadWrite.All, Item.ReadWrite.All
FABRIC_API_ID="00000009-0000-0000-c000-000000000000"
az ad app permission add --id "${APP_ID}" \
  --api "${FABRIC_API_ID}" \
  --api-permissions "f3076109-ca66-412a-be10-d4f693571f57=Scope" 2>/dev/null || echo "  (permission may already exist)"

# Grant admin consent
echo "Granting admin consent..."
az ad app permission admin-consent --id "${APP_ID}" 2>/dev/null || \
  echo "  (admin consent may require Global Admin - grant manually in Azure Portal)"

# Configure OIDC federation for GitHub Actions
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "OWNER/REPO")
echo ""
echo "Configuring OIDC federation for GitHub Actions..."
for ENV in dev prod; do
  echo "  → Environment: ${ENV}"
  az ad app federated-credential create --id "${APP_ID}" --parameters "{
    \"name\": \"github-${ENV}\",
    \"issuer\": \"https://token.actions.githubusercontent.com\",
    \"subject\": \"repo:${REPO}:environment:${ENV}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }" 2>/dev/null || echo "    (credential may already exist)"
done

# Assign Contributor role on subscription for Terraform
echo ""
echo "Assigning Contributor role..."
az role assignment create --assignee "${APP_ID}" \
  --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}" 2>/dev/null || echo "  (role may already exist)"

# Configure GitHub secrets
if command -v gh >/dev/null 2>&1; then
  echo ""
  echo "Configuring GitHub repository secrets..."
  gh secret set AZURE_CLIENT_ID --body "${APP_ID}"
  gh secret set AZURE_TENANT_ID --body "${TENANT_ID}"
  gh secret set AZURE_SUBSCRIPTION_ID --body "${SUBSCRIPTION_ID}"
  echo "GitHub secrets configured."
fi

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "App Registration: ${APP_NAME}"
echo "Client ID: ${APP_ID}"
echo "Tenant ID: ${TENANT_ID}"
echo "Subscription: ${SUBSCRIPTION_ID}"
echo ""
echo "Manual steps remaining:"
echo "  1. In Azure Portal → Microsoft Fabric Admin Portal:"
echo "     - Enable 'Service principals can use Fabric APIs'"
echo "     - Add the SP to a security group with Fabric access"
echo "  2. In GitHub → Settings → Environments:"
echo "     - Create 'dev' and 'prod' environments"
echo "     - Add required reviewers to 'prod'"
echo "  3. Run: cd infra/environments/dev && terraform init && terraform plan"
