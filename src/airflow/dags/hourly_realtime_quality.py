"""
Contoso Hourly Real-Time Data Quality DAG

Runs every hour. Validates the health and quality of real-time data
streams flowing through the Fabric Eventhouse:
  1. Data freshness — are events still arriving?
  2. Row count validation — are volumes within expected thresholds?
  3. Schema drift detection — have incoming fields changed?
  4. Alerts — Teams / email notification on quality failures.

Airflow Variables required:
  - fabric_realtime_workspace_id  : Workspace ID for the real-time analytics workspace
  - eventhouse_connection_string  : Eventhouse query service URI
  - quality_alert_webhook         : Microsoft Teams incoming-webhook URL
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "contoso-data-team",
    "depends_on_past": False,
    "email": ["data-team@contoso.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


# ---------------------------------------------------------------------------
# Helper: execute a KQL query against the Eventhouse via the Fabric REST API
# ---------------------------------------------------------------------------
def _run_kql_query(query: str) -> list[dict]:
    """Execute a KQL query using the Fabric REST API and return rows."""
    import json

    import requests
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token

    workspace_id = Variable.get("fabric_realtime_workspace_id")
    kqldb_id = Variable.get("kql_database_id")

    response = requests.post(
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
        f"/kqlDatabases/{kqldb_id}/executeQuery",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=60,
    )
    response.raise_for_status()
    return json.loads(response.text).get("results", [])


# ---------------------------------------------------------------------------
# Helper: send a Teams / webhook alert
# ---------------------------------------------------------------------------
def _send_alert(title: str, message: str, severity: str = "warning") -> None:
    """Post an alert to Microsoft Teams via incoming webhook."""
    import requests

    webhook_url = Variable.get("quality_alert_webhook")
    color = {"critical": "FF0000", "warning": "FFA500", "info": "0078D4"}

    payload = {
        "@type": "MessageCard",
        "themeColor": color.get(severity, "FFA500"),
        "title": title,
        "text": message,
    }
    requests.post(webhook_url, json=payload, timeout=30)


# ---------------------------------------------------------------------------
# Task implementations
# ---------------------------------------------------------------------------
def check_data_freshness(**context):
    """Verify that key real-time tables have received events recently."""
    tables = {
        "RealtimeSales": 15,  # max minutes since last event
        "IoTSensorReadings": 10,
        "InventorySnapshot": 60,
    }

    stale_tables = []
    for table, max_lag_min in tables.items():
        query = (
            f"{table} | summarize LastEvent=max(Timestamp) "
            f"| extend LagMinutes=datetime_diff('minute', now(), LastEvent)"
        )
        rows = _run_kql_query(query)
        if rows:
            lag = rows[0].get("LagMinutes", 9999)
            if lag > max_lag_min:
                stale_tables.append(
                    f"**{table}**: last event {lag} min ago (threshold {max_lag_min} min)"
                )

    if stale_tables:
        msg = "Data freshness check FAILED:\\n" + "\\n".join(stale_tables)
        _send_alert("🕐 Data Freshness Alert", msg, severity="critical")
        raise ValueError(f"Stale tables detected: {stale_tables}")

    context["ti"].xcom_push(key="freshness_status", value="all_tables_fresh")


def check_row_counts(**context):
    """Validate hourly row counts are within expected thresholds."""
    expectations = {
        "RealtimeSales": {"min": 100, "max": 500000},
        "IoTSensorReadings": {"min": 50, "max": 100000},
    }

    violations = []
    for table, bounds in expectations.items():
        query = (
            f"{table} | where Timestamp > ago(1h) "
            f"| summarize RowCount=count()"
        )
        rows = _run_kql_query(query)
        if rows:
            count = rows[0].get("RowCount", 0)
            if count < bounds["min"]:
                violations.append(
                    f"**{table}**: {count} rows (expected ≥{bounds['min']})"
                )
            elif count > bounds["max"]:
                violations.append(
                    f"**{table}**: {count} rows (expected ≤{bounds['max']})"
                )

    if violations:
        msg = "Row count validation FAILED:\\n" + "\\n".join(violations)
        _send_alert("📊 Row Count Alert", msg, severity="warning")
        raise ValueError(f"Row count violations: {violations}")

    context["ti"].xcom_push(key="row_count_status", value="counts_within_range")


def check_schema_drift(**context):
    """Detect unexpected schema changes in incoming streams."""
    expected_schemas = {
        "RealtimeSales": {
            "TransactionId",
            "Timestamp",
            "StoreId",
            "ProductId",
            "Quantity",
            "UnitPrice",
            "TotalAmount",
            "PaymentMethod",
            "CustomerId",
        },
        "IoTSensorReadings": {
            "SensorId",
            "StoreId",
            "SensorType",
            "Temperature",
            "Humidity",
            "Timestamp",
        },
    }

    drift_issues = []
    for table, expected_cols in expected_schemas.items():
        query = (
            f"{table} | getschema "
            f"| project ColumnName"
        )
        rows = _run_kql_query(query)
        actual_cols = {row.get("ColumnName") for row in rows} if rows else set()

        missing = expected_cols - actual_cols
        added = actual_cols - expected_cols

        if missing:
            drift_issues.append(
                f"**{table}** — missing columns: {', '.join(sorted(missing))}"
            )
        if added:
            drift_issues.append(
                f"**{table}** — unexpected new columns: {', '.join(sorted(added))}"
            )

    if drift_issues:
        msg = "Schema drift detected:\\n" + "\\n".join(drift_issues)
        _send_alert("⚠️ Schema Drift Alert", msg, severity="warning")
        raise ValueError(f"Schema drift: {drift_issues}")

    context["ti"].xcom_push(key="schema_status", value="schema_stable")


def quality_report(**context):
    """Compile a quality summary and push to XCom."""
    ti = context["ti"]
    summary = {
        "freshness": ti.xcom_pull(
            task_ids="data_freshness.check_data_freshness",
            key="freshness_status",
        ),
        "row_counts": ti.xcom_pull(
            task_ids="row_count_validation.check_row_counts",
            key="row_count_status",
        ),
        "schema": ti.xcom_pull(
            task_ids="schema_drift.check_schema_drift",
            key="schema_status",
        ),
    }
    _send_alert(
        "✅ Hourly Quality Check Passed",
        f"All checks passed: {summary}",
        severity="info",
    )


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="contoso_hourly_realtime_quality",
    default_args=default_args,
    description="Hourly real-time data quality: freshness, volume, schema",
    schedule_interval="@hourly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["contoso", "data-quality", "hourly", "real-time"],
    max_active_runs=1,
) as dag:

    with TaskGroup("data_freshness") as freshness_group:
        freshness_task = PythonOperator(
            task_id="check_data_freshness",
            python_callable=check_data_freshness,
        )

    with TaskGroup("row_count_validation") as row_count_group:
        row_count_task = PythonOperator(
            task_id="check_row_counts",
            python_callable=check_row_counts,
        )

    with TaskGroup("schema_drift") as schema_group:
        schema_task = PythonOperator(
            task_id="check_schema_drift",
            python_callable=check_schema_drift,
        )

    report = PythonOperator(
        task_id="quality_report",
        python_callable=quality_report,
        trigger_rule="all_success",
    )

    # Freshness, row counts, and schema checks run in parallel;
    # summary report runs after all three succeed.
    [freshness_group, row_count_group, schema_group] >> report
