# Tales & Timber Retail GraphQL API — Setup Guide

This guide walks through creating, configuring, and consuming the Tales & Timber GraphQL API in Microsoft Fabric.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create the GraphQL API in Fabric Portal](#create-the-graphql-api-in-fabric-portal)
3. [Connect to the Warehouse Data Source](#connect-to-the-warehouse-data-source)
4. [Import the Schema](#import-the-schema)
5. [Test with the Built-in Explorer](#test-with-the-built-in-explorer)
6. [Authentication Setup](#authentication-setup)
7. [Frontend Integration](#frontend-integration)
8. [Terraform Provisioning](#terraform-provisioning)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Microsoft Fabric workspace with **Contributor** or **Admin** role
- A provisioned Fabric **Warehouse** (`tt_warehouse`) or **Lakehouse** (`lh_gold`) with populated tables
- Microsoft Entra ID tenant with appropriate app registrations
- (Optional) Terraform with `microsoft/fabric` provider >= 1.8 for IaC provisioning

---

## Create the GraphQL API in Fabric Portal

1. Navigate to your Fabric workspace (e.g., `tt-data-warehouse-dev`)
2. Click **+ New item** → select **GraphQL API** under the "API" section
3. Enter the display name: `tt_retail_api`
4. Enter a description: `Unified GraphQL API for Tales & Timber retail data — products, stores, customers, sales, and inventory`
5. Click **Create**

The API item is created and you'll be taken to the schema editor.

---

## Connect to the Warehouse Data Source

The GraphQL API needs a data source to resolve queries against.

### Option A: Fabric Warehouse (Recommended)

1. In the GraphQL API editor, click **Connect data source**
2. Select **Microsoft Fabric Warehouse**
3. Choose `tt_warehouse` from the workspace
4. Fabric will introspect the warehouse schema and present available tables:
   - `dims.dim_customer`
   - `dims.dim_product`
   - `dims.dim_store`
   - `dims.dim_date`
   - `facts.fact_sales`
   - `facts.fact_inventory`
5. Select all tables → click **Connect**

### Option B: Gold Lakehouse (DirectLake)

1. Click **Connect data source** → select **Microsoft Fabric Lakehouse**
2. Choose `lh_gold` from the `tt-data-engineering-{env}` workspace
3. Select the Delta tables exposed through the gold layer
4. Click **Connect**

---

## Import the Schema

After connecting the data source, Fabric auto-generates a basic schema. You can enhance it with the Tales & Timber schema definitions:

1. Open the **Schema** tab in the GraphQL API editor
2. Click **Edit schema** (switch to SDL mode)
3. Replace or merge with the contents of:
   - `src/graphql/schema/retail_api.graphql` — Query types and object types
   - `src/graphql/schema/mutations.graphql` — Mutation types
4. Click **Save & validate**

Fabric will validate that:
- All types reference columns that exist in the connected data source
- Relationships (joins) are valid
- Input types match expected patterns

### Resolver Configuration

Fabric auto-generates resolvers for types that map directly to tables. For computed fields and aggregations (e.g., `storePerformance`, `salesSummary`, `topProducts`), you may need to:

1. Create **views** in the warehouse that pre-aggregate the data
2. Map the GraphQL type to the view instead of the base table
3. Or use **stored procedures** as custom resolvers

See `src/warehouse/views/` for pre-built aggregation views.

---

## Test with the Built-in Explorer

Fabric provides an integrated GraphQL explorer (similar to GraphiQL):

1. In the GraphQL API editor, click **Run** or **Test API**
2. The explorer opens with schema auto-complete
3. Try this sample query:

```graphql
query {
  products(category: "Electronics", first: 5) {
    items {
      productId
      name
      brand
      unitPrice
      isActive
    }
    totalCount
  }
}
```

4. Click **▶ Execute** — results appear in the right pane
5. Use the **Docs** panel (right side) to browse the full schema

### Testing Mutations

```graphql
mutation {
  createOrder(input: {
    customerId: "CUST-01234"
    storeId: "STR-0042"
    channel: "In-Store"
    paymentMethod: "Credit Card"
    items: [
      { productId: "PRD-00142", quantity: 1 }
    ]
  }) {
    success
    transactionId
    totalAmount
    errors { code message }
  }
}
```

---

## Authentication Setup

### For Interactive Users (Authorization Code Flow)

Users authenticate via Entra ID and receive a bearer token:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOi...
```

### For Service-to-Service (Client Credentials Flow)

1. Register an app in Entra ID
2. Grant the app **Fabric API** permissions
3. Add the app's service principal to the Fabric workspace with **Contributor** role
4. Acquire a token:

```bash
curl -X POST "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token" \
  -d "client_id={app_client_id}" \
  -d "client_secret={app_client_secret}" \
  -d "scope=https://analysis.windows.net/powerbi/api/.default" \
  -d "grant_type=client_credentials"
```

---

## Frontend Integration

### JavaScript / TypeScript (fetch)

```typescript
const GRAPHQL_ENDPOINT =
  "https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/graphqlApis/{api_id}/graphql";

async function queryTales & TimberAPI<T>(
  query: string,
  variables?: Record<string, unknown>,
  accessToken: string
): Promise<T> {
  const response = await fetch(GRAPHQL_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ query, variables }),
  });

  if (!response.ok) {
    throw new Error(`GraphQL request failed: ${response.status} ${response.statusText}`);
  }

  const json = await response.json();
  if (json.errors) {
    throw new Error(`GraphQL errors: ${JSON.stringify(json.errors)}`);
  }

  return json.data as T;
}

// Example: Fetch top products
const data = await queryTales & TimberAPI(
  `query TopProducts($limit: Int!, $start: String!, $end: String!) {
    topProducts(limit: $limit, dateRange: { startDate: $start, endDate: $end }) {
      rank
      product { productId name category unitPrice }
      totalRevenue
      totalQuantity
    }
  }`,
  { limit: 10, start: "2025-07-01", end: "2025-07-31" },
  accessToken
);
```

### React Hook Example

```typescript
import { useEffect, useState } from "react";
import { useMsal } from "@azure/msal-react";

function useTales & TimberQuery<T>(query: string, variables?: Record<string, unknown>) {
  const { instance } = useMsal();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const tokenResponse = await instance.acquireTokenSilent({
          scopes: ["https://analysis.windows.net/powerbi/api/.default"],
        });
        const result = await queryTales & TimberAPI<T>(
          query,
          variables,
          tokenResponse.accessToken
        );
        setData(result);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [query, JSON.stringify(variables)]);

  return { data, loading, error };
}
```

---

## Terraform Provisioning

The GraphQL API item can be provisioned via Terraform:

```hcl
module "graphql_api" {
  source = "../../modules/fabric-graphql"

  workspace_id    = module.fabric_workspaces["data-warehouse"].workspace_id
  display_name    = "${var.project_prefix}_retail_api"
  description     = "Tales & Timber Retail GraphQL API (${var.environment})"
  data_source_id  = module.warehouse.warehouse_id
  data_source_type = "warehouse"
}
```

> **Note:** Terraform creates the API item container. Data-source binding and schema import require post-provisioning steps (portal or REST API). See the CI/CD workflow in `.github/workflows/` for automated schema deployment.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No data source connected" | Re-run data source connection wizard; ensure warehouse is in the same capacity |
| Schema validation errors | Check that table/column names in `.graphql` files match the warehouse schema exactly |
| 401 Unauthorized | Verify the bearer token has `Fabric.ReadWrite.All` scope and the app has workspace access |
| 429 Too Many Requests | You've exceeded the rate limit; implement exponential backoff or request a premium tier |
| Slow queries on aggregations | Create pre-aggregated views in the warehouse (see `src/warehouse/views/`) |
| CORS errors in browser | Update the allowed_origins list in the Fabric portal or `api_config.json` |
| Mutations not working | Ensure the authenticated identity has write permissions (Contributor role) on the workspace |
