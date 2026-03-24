# Bootstrap — Service Principal for Fabric Terraform Automation

This bootstrap configuration creates an Azure AD application and service principal
that Terraform uses to manage Microsoft Fabric and Azure resources.

## Prerequisites

- **Azure CLI** authenticated with an account that has:
  - `Application Administrator` or `Global Administrator` role in Azure AD
  - `Owner` or `User Access Administrator` role on the target subscription
- **Terraform** >= 1.9 installed

## Steps

### 1. Authenticate with Azure CLI

```bash
az login
az account set --subscription "78118340-da1a-4f38-a514-1afe4d4378c0"
```

### 2. Initialize and apply the bootstrap

```bash
cd infra/bootstrap
terraform init
terraform plan -var="subscription_id=78118340-da1a-4f38-a514-1afe4d4378c0"
terraform apply -var="subscription_id=78118340-da1a-4f38-a514-1afe4d4378c0"
```

### 3. Capture the outputs

```bash
# Get the client ID and tenant ID
terraform output client_id
terraform output tenant_id
terraform output service_principal_object_id

# Get the client secret (sensitive)
terraform output -raw client_secret
```

### 4. Configure Fabric Admin

After the SPN is created, you must grant it Fabric Admin permissions:

1. Go to the [Microsoft Fabric Admin Portal](https://app.fabric.microsoft.com/admin-portal)
2. Navigate to **Tenant settings** → **Developer settings**
3. Enable **Service principals can use Fabric APIs**
4. Add the SPN to the allowed security group (or allow all)

Alternatively, assign the SPN to the **Fabric Administrator** role in Azure AD:

```bash
# Get the SPN object ID from terraform output
SPN_OBJECT_ID=$(terraform output -raw service_principal_object_id)

# Assign Fabric Administrator role (requires Global Admin)
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
  --body "{
    \"@odata.type\": \"#microsoft.graph.unifiedRoleAssignment\",
    \"principalId\": \"${SPN_OBJECT_ID}\",
    \"roleDefinitionId\": \"a9ea8996-122f-4c74-9520-8edcd192826c\",
    \"directoryScopeId\": \"/\"
  }"
```

### 5. Set environment variables for Terraform

```bash
export ARM_CLIENT_ID="<client_id from output>"
export ARM_CLIENT_SECRET="<client_secret from output>"
export ARM_TENANT_ID="<tenant_id from output>"
export ARM_SUBSCRIPTION_ID="78118340-da1a-4f38-a514-1afe4d4378c0"
```

### 6. Deploy dev/prod environments

```bash
cd ../environments/dev
terraform init
terraform plan
terraform apply
```

## Notes

- The client secret expires on 2026-12-31. Rotate before expiry.
- The SPN is assigned `Contributor` at the subscription level. Tighten scope for production.
- Add the SPN object ID to the `admin_members` variable in dev/prod environments.
