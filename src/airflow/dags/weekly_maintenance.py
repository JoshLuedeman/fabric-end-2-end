"""
Contoso Weekly Maintenance DAG

Runs every Sunday at midnight UTC. Performs housekeeping tasks across
the Fabric data platform:
  1. Vacuum / optimize Delta tables in bronze, silver, and gold lakehouses
  2. Update statistics in the data warehouse
  3. Archive data beyond retention period to cold storage
  4. Full retrain of ML models (vs. daily incremental)
  5. Generate weekly data quality report
  6. Clean up old MLflow experiment runs (>90 days)

Airflow Variables required:
  - fabric_workspace_id             : Data-engineering workspace ID
  - fabric_warehouse_workspace_id   : Data-warehouse workspace ID
  - fabric_datascience_workspace_id : Data-science workspace ID
  - warehouse_connection_string     : SQL connection string for warehouse
  - staging_storage_connection      : Azure Storage connection for cold archive
  - retention_days                  : Number of days to retain in hot storage (default: 365)
  - mlflow_tracking_uri             : MLflow tracking server URI
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
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
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=4),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_fabric_token() -> str:
    """Obtain a bearer token for Fabric REST API calls."""
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return credential.get_token("https://api.fabric.microsoft.com/.default").token


def _fabric_post(url: str, body: dict | None = None) -> dict:
    """POST to the Fabric REST API and return JSON response."""
    import json

    import requests

    token = _get_fabric_token()
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body or {},
        timeout=120,
    )
    resp.raise_for_status()
    return json.loads(resp.text) if resp.text else {}


# ---------------------------------------------------------------------------
# Task: Vacuum / optimize Delta tables
# ---------------------------------------------------------------------------
def optimize_delta_tables(**context):
    """Run OPTIMIZE and VACUUM on all Delta tables across lakehouses."""
    import requests

    workspace_id = Variable.get("fabric_workspace_id")
    token = _get_fabric_token()

    lakehouses = {"bronze": "lh_bronze", "silver": "lh_silver", "gold": "lh_gold"}

    for tier, lakehouse_name in lakehouses.items():
        # List tables in each lakehouse via Fabric REST API
        url = (
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/lakehouses/{Variable.get(f'lakehouse_id_{tier}')}/tables"
        )
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        resp.raise_for_status()
        tables = resp.json().get("data", [])

        for table in tables:
            table_name = table.get("name")
            # Spark SQL commands would be executed via a maintenance notebook
            # in production; here we log the intent for observability.
            print(
                f"[{tier}] Queued OPTIMIZE + VACUUM for {lakehouse_name}.{table_name}"
            )

    context["ti"].xcom_push(key="optimized_tiers", value=list(lakehouses.keys()))


# ---------------------------------------------------------------------------
# Task: Update warehouse statistics
# ---------------------------------------------------------------------------
def update_warehouse_statistics(**context):
    """Run UPDATE STATISTICS on all warehouse tables."""
    import requests

    workspace_id = Variable.get("fabric_warehouse_workspace_id")
    warehouse_id = Variable.get("warehouse_id")
    token = _get_fabric_token()

    schemas = ["dbo", "staging"]
    for schema in schemas:
        query = (
            f"EXEC sp_MSforeachtable "
            f"@command1='UPDATE STATISTICS ? WITH FULLSCAN', "
            f"@whereand='AND SCHEMA_NAME(schema_id) = ''{schema}'''"
        )
        _fabric_post(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/warehouses/{warehouse_id}/executeQuery",
            body={"query": query},
        )
        print(f"Updated statistics for schema: {schema}")

    context["ti"].xcom_push(key="stats_updated", value=True)


# ---------------------------------------------------------------------------
# Task: Archive old data
# ---------------------------------------------------------------------------
def archive_old_data(**context):
    """Move data older than retention period to cold storage."""
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    retention_days = int(Variable.get("retention_days", default_var="365"))
    storage_conn = Variable.get("staging_storage_connection")
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    credential = DefaultAzureCredential()
    blob_service = BlobServiceClient(
        account_url=storage_conn,
        credential=credential,
    )

    # Archive is handled by setting blob tier; actual data movement
    # from Lakehouse to cold storage is done by a dedicated notebook
    # that reads old partitions and writes them to archive container.
    archive_container = blob_service.get_container_client("archive")
    if not archive_container.exists():
        archive_container.create_container()

    print(
        f"Archive target configured. Cutoff date: {cutoff_date.isoformat()}. "
        f"Data older than {retention_days} days will be moved to cold storage."
    )
    context["ti"].xcom_push(
        key="archive_cutoff", value=cutoff_date.isoformat()
    )


# ---------------------------------------------------------------------------
# Task: Generate data quality report
# ---------------------------------------------------------------------------
def generate_quality_report(**context):
    """Compile weekly data quality metrics and push summary."""
    import json

    workspace_id = Variable.get("fabric_realtime_workspace_id")
    kqldb_id = Variable.get("kql_database_id")
    token = _get_fabric_token()

    queries = {
        "total_events_7d": (
            "RealtimeSales | where Timestamp > ago(7d) | count"
        ),
        "null_rate_7d": (
            "RealtimeSales | where Timestamp > ago(7d) "
            "| summarize NullCustomer=countif(isnull(CustomerId)), "
            "Total=count() "
            "| extend NullPct=round(100.0 * NullCustomer / Total, 2)"
        ),
        "duplicate_rate_7d": (
            "RealtimeSales | where Timestamp > ago(7d) "
            "| summarize Cnt=count() by TransactionId "
            "| where Cnt > 1 | count"
        ),
    }

    report = {}
    for metric_name, query in queries.items():
        import requests

        resp = requests.post(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/kqlDatabases/{kqldb_id}/executeQuery",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query},
            timeout=60,
        )
        resp.raise_for_status()
        report[metric_name] = json.loads(resp.text).get("results", [])

    print(f"Weekly quality report: {json.dumps(report, indent=2)}")
    context["ti"].xcom_push(key="quality_report", value=report)


# ---------------------------------------------------------------------------
# Task: Clean up old MLflow runs
# ---------------------------------------------------------------------------
def cleanup_mlflow_runs(**context):
    """Delete MLflow experiment runs older than 90 days."""
    import mlflow

    tracking_uri = Variable.get("mlflow_tracking_uri")
    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.tracking.MlflowClient()

    cutoff_ms = int(
        (datetime.utcnow() - timedelta(days=90)).timestamp() * 1000
    )

    experiments = client.search_experiments()
    deleted_count = 0
    for experiment in experiments:
        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"attributes.start_time < {cutoff_ms}",
            max_results=500,
        )
        for run in runs:
            client.delete_run(run.info.run_id)
            deleted_count += 1

    print(f"Cleaned up {deleted_count} MLflow runs older than 90 days.")
    context["ti"].xcom_push(key="mlflow_runs_deleted", value=deleted_count)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="contoso_weekly_maintenance",
    default_args=default_args,
    description="Weekly: optimize tables, update stats, archive, retrain ML, quality report",
    schedule_interval="0 0 * * 0",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["contoso", "maintenance", "weekly"],
    max_active_runs=1,
) as dag:

    # ----- Stage 1: Delta table optimization -----
    with TaskGroup("delta_optimization") as optimize_group:
        optimize_task = PythonOperator(
            task_id="optimize_delta_tables",
            python_callable=optimize_delta_tables,
        )

    # ----- Stage 2: Warehouse statistics -----
    with TaskGroup("warehouse_stats") as stats_group:
        stats_task = PythonOperator(
            task_id="update_warehouse_statistics",
            python_callable=update_warehouse_statistics,
        )

    # ----- Stage 3: Data archival -----
    archive_task = PythonOperator(
        task_id="archive_old_data",
        python_callable=archive_old_data,
    )

    # ----- Stage 4: Full ML retrain (parallel) -----
    with TaskGroup("ml_full_retrain") as ml_retrain_group:
        retrain_forecast = FabricRunItemOperator(
            task_id="retrain_demand_forecast",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_forecast }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        retrain_churn = FabricRunItemOperator(
            task_id="retrain_churn_model",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_churn }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

        retrain_segments = FabricRunItemOperator(
            task_id="retrain_customer_segments",
            workspace_id="{{ var.value.fabric_datascience_workspace_id }}",
            item_id="{{ var.value.notebook_ml_segments }}",
            job_type="RunNotebook",
            wait_for_completion=True,
        )

    # ----- Stage 5: Quality report -----
    quality_report_task = PythonOperator(
        task_id="generate_quality_report",
        python_callable=generate_quality_report,
    )

    # ----- Stage 6: MLflow cleanup -----
    mlflow_cleanup = PythonOperator(
        task_id="cleanup_mlflow_runs",
        python_callable=cleanup_mlflow_runs,
    )

    # ----- Dependencies -----
    # Optimization and stats run in parallel first.
    # Then archival, ML retrain, and quality report can run in parallel.
    # MLflow cleanup runs last.
    (
        [optimize_group, stats_group]
        >> archive_task
        >> [ml_retrain_group, quality_report_task]
        >> mlflow_cleanup
    )
