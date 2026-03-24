# Contoso Retail — Apache Airflow DAGs

These DAGs are deployed to **Fabric's Managed Airflow** ([Apache Airflow Jobs](https://learn.microsoft.com/fabric/data-factory/apache-airflow-jobs)) and orchestrate the full Contoso data platform.

## DAG Overview

| DAG ID | Schedule | Description |
|--------|----------|-------------|
| `contoso_daily_etl` | Daily 02:00 UTC | Full pipeline: OLTP CDC → Bronze → Silver → Gold → Warehouse → ML refresh |
| `contoso_hourly_realtime_quality` | Hourly | Data freshness, volume, and schema drift checks on Eventhouse streams |
| `contoso_weekly_maintenance` | Sunday 00:00 UTC | Delta OPTIMIZE/VACUUM, warehouse stats, archival, full ML retrain, cleanup |

## Relationship to Fabric Pipelines

The existing Fabric Data Pipelines remain in `src/pipelines/`:

- `pl_ingest_daily.json` — ad-hoc ingestion runs
- `pl_transform_medallion.json` — ad-hoc medallion transforms
- `pl_load_warehouse.json` — ad-hoc warehouse loads

**These Airflow DAGs are the recommended production orchestration layer.** They replace the three separate pipelines with a single, dependency-aware workflow that includes retries, alerting, and ML model refresh. The Fabric pipelines remain available for simpler ad-hoc or debugging runs.

## Configuring Airflow Variables

All notebook and pipeline item IDs are referenced via [Airflow Variables](https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html). Set these in the Fabric Managed Airflow UI (**Apache Airflow Jobs → Environment → Variables**) or via the Airflow CLI.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `fabric_workspace_id` | Data-engineering workspace ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `fabric_warehouse_workspace_id` | Data-warehouse workspace ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `fabric_realtime_workspace_id` | Real-time analytics workspace ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `fabric_datascience_workspace_id` | Data-science workspace ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ingest_sqldb` | CDC extraction notebook item ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ingest_dimensions` | `ingest_dimensions.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ingest_sales` | `ingest_sales.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ingest_inventory` | `ingest_inventory.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_transform_sales` | `transform_sales.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_transform_customers` | `transform_customers.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_transform_supply` | `transform_supply_chain.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_dim_customer` | `dim_customer.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_dim_product` | `dim_product.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_dim_store` | `dim_store.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_fact_sales` | `fact_sales.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_fact_inventory` | `fact_inventory.py` notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `pipeline_load_warehouse` | `pl_load_warehouse` pipeline item ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ml_forecast` | Demand forecasting notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ml_churn` | Churn prediction notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `notebook_ml_segments` | Customer segmentation notebook ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `kql_database_id` | Eventhouse KQL database ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `quality_alert_webhook` | Teams incoming-webhook URL | `https://contoso.webhook.office.com/...` |
| `retention_days` | Hot-storage retention (default 365) | `365` |
| `mlflow_tracking_uri` | MLflow tracking server URI | `https://mlflow.contoso.com` |

### How to set variables

```bash
# Via Airflow CLI (inside the Managed Airflow environment)
airflow variables set fabric_workspace_id "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Or import from JSON
airflow variables import airflow_variables.json
```

## Dependencies

See `requirements.txt` for Python packages required in the Managed Airflow environment. The key dependency is:

```
apache-airflow-providers-microsoft-fabric>=1.0.0
```

This provides `FabricRunItemOperator` which triggers Fabric notebooks and pipelines directly from Airflow.

## Deployment

1. **Create an Apache Airflow Job** in your Fabric workspace.
2. **Upload DAG files** from `src/airflow/dags/` to the Airflow Job's DAG folder.
3. **Install requirements** by adding `requirements.txt` contents to the Airflow environment configuration.
4. **Set Airflow Variables** as documented above.
5. **Enable DAGs** in the Airflow UI — they are paused by default.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Airflow (Orchestrator)              │
├──────────┬──────────────┬───────────────────────────┤
│  Daily   │    Hourly    │         Weekly             │
│  ETL     │   Quality    │       Maintenance          │
├──────────┴──────────────┴───────────────────────────┤
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐             │
│  │ Fabric  │  │ Fabric  │  │  Fabric  │             │
│  │Notebooks│  │Pipelines│  │REST APIs │             │
│  └────┬────┘  └────┬────┘  └────┬─────┘             │
│       │            │            │                    │
│  ┌────▼────┐  ┌────▼────┐  ┌───▼──────┐            │
│  │Lakehouse│  │Warehouse│  │Eventhouse│            │
│  │ Bronze  │  │         │  │  KQL DB  │            │
│  │ Silver  │  │         │  │          │            │
│  │  Gold   │  │         │  │          │            │
│  └─────────┘  └─────────┘  └──────────┘            │
└─────────────────────────────────────────────────────┘
```
