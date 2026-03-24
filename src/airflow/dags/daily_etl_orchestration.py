"""
Contoso Daily ETL Orchestration DAG

Runs daily at 2:00 AM UTC. Orchestrates the full data pipeline:
OLTP CDC Extract → Bronze Ingest → Silver Transform → Gold Build → Warehouse Load → ML Refresh

This DAG replaces the three separate Fabric pipelines with a single
orchestrated workflow, demonstrating metadata-driven pipeline patterns.

Fabric Pipelines replaced:
  - pl_ingest_daily.json      → extract_cdc + bronze_ingestion stages
  - pl_transform_medallion.json → silver_transforms + gold stages
  - pl_load_warehouse.json    → load_warehouse stage

Airflow Variables required (set in Fabric Managed Airflow UI):
  - fabric_workspace_id           : Fabric data-engineering workspace ID
  - fabric_warehouse_workspace_id : Fabric data-warehouse workspace ID
  - fabric_realtime_workspace_id  : Fabric real-time workspace ID
  - fabric_datascience_workspace_id : Fabric data-science workspace ID
  - notebook_ingest_sqldb         : Item ID for the CDC extraction notebook
  - notebook_ingest_dimensions    : Item ID for ingest_dimensions.py notebook
  - notebook_ingest_sales         : Item ID for ingest_sales.py notebook
  - notebook_ingest_inventory     : Item ID for ingest_inventory.py notebook
  - notebook_transform_sales      : Item ID for transform_sales.py notebook
  - notebook_transform_customers  : Item ID for transform_customers.py notebook
  - notebook_transform_supply     : Item ID for transform_supply_chain.py notebook
  - notebook_dim_customer         : Item ID for dim_customer.py notebook
  - notebook_dim_product          : Item ID for dim_product.py notebook
  - notebook_dim_store            : Item ID for dim_store.py notebook
  - notebook_fact_sales           : Item ID for fact_sales.py notebook
  - notebook_fact_inventory       : Item ID for fact_inventory.py notebook
  - pipeline_load_warehouse       : Item ID for pl_load_warehouse pipeline
  - notebook_ml_forecast          : Item ID for demand forecasting notebook
  - notebook_ml_churn             : Item ID for churn prediction notebook
  - notebook_ml_segments          : Item ID for customer segmentation notebook
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.microsoft.fabric.operators.fabric import (
    FabricRunItemOperator,
)
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "contoso-data-team",
    "depends_on_past": False,
    "email": ["data-team@contoso.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="contoso_daily_etl",
    default_args=default_args,
    description="Daily ETL: OLTP → Bronze → Silver → Gold → Warehouse → ML",
    schedule_interval="0 2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["contoso", "etl", "daily", "production"],
    max_active_runs=1,
) as dag:

    # ---------------------------------------------------------------
    # Stage 1: Extract from OLTP (CDC)
    # ---------------------------------------------------------------
    extract_cdc = FabricRunItemOperator(
        task_id="extract_cdc_from_sqldb",
        workspace_id="{{ var.value.fabric_workspace_id }}",
        item_id="{{ var.value.notebook_ingest_sqldb }}",
        job_type="RunNotebook",
        wait_for_completion=True,
    )

    # ---------------------------------------------------------------
    # Stage 2: Bronze ingestion (parallel)
    # ---------------------------------------------------------------
    with TaskGroup("bronze_ingestion") as bronze_group:
        ingest_dims = FabricRunItemOperator(
            task_id="ingest_dimensions",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_ingest_dimensions }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        ingest_sales = FabricRunItemOperator(
            task_id="ingest_sales",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_ingest_sales }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        ingest_inventory = FabricRunItemOperator(
            task_id="ingest_inventory",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_ingest_inventory }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    # ---------------------------------------------------------------
    # Stage 3: Silver transforms (parallel)
    # ---------------------------------------------------------------
    with TaskGroup("silver_transforms") as silver_group:
        transform_sales = FabricRunItemOperator(
            task_id="transform_sales",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_transform_sales }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        transform_customers = FabricRunItemOperator(
            task_id="transform_customers",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_transform_customers }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        transform_supply = FabricRunItemOperator(
            task_id="transform_supply_chain",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_transform_supply }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    # ---------------------------------------------------------------
    # Stage 4: Gold dimensional model
    # Dimensions must complete before facts (facts reference dim keys).
    # ---------------------------------------------------------------
    with TaskGroup("gold_dimensions") as gold_dims:
        dim_customer = FabricRunItemOperator(
            task_id="dim_customer",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_dim_customer }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        dim_product = FabricRunItemOperator(
            task_id="dim_product",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_dim_product }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        dim_store = FabricRunItemOperator(
            task_id="dim_store",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_dim_store }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    with TaskGroup("gold_facts") as gold_facts:
        fact_sales = FabricRunItemOperator(
            task_id="fact_sales",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_fact_sales }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        fact_inventory = FabricRunItemOperator(
            task_id="fact_inventory",
            workspace_id="{{ var.value.fabric_workspace_id }}",
            item_id="{{ var.value.notebook_fact_inventory }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    # ---------------------------------------------------------------
    # Stage 5: Warehouse load
    # Uses the existing pl_load_warehouse Fabric pipeline.
    # ---------------------------------------------------------------
    load_warehouse = FabricRunItemOperator(
        task_id="load_warehouse",
        workspace_id="{{ var.value.fabric_warehouse_workspace_id }}",
        item_id="{{ var.value.pipeline_load_warehouse }}",
        job_type="Pipeline",
        wait_for_completion=True,
    )

    # ---------------------------------------------------------------
    # Stage 6: ML model refresh (parallel)
    # ---------------------------------------------------------------
    with TaskGroup("ml_refresh") as ml_group:
        refresh_forecast = FabricRunItemOperator(
            task_id="ml_demand_forecast",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_forecast }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        refresh_churn = FabricRunItemOperator(
            task_id="ml_churn_prediction",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_churn }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        refresh_segments = FabricRunItemOperator(
            task_id="ml_customer_segments",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_segments }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    # ---------------------------------------------------------------
    # DAG dependency chain
    # ---------------------------------------------------------------
    (
        extract_cdc
        >> bronze_group
        >> silver_group
        >> gold_dims
        >> gold_facts
        >> load_warehouse
        >> ml_group
    )
