# Fabric Notebook: Metadata-Driven Ingestion (Bronze Layer)
# Reads the PipelineMetadata table from the operational SQL Database and
# dynamically ingests ALL active sources into the bronze Lakehouse.
#
# This replaces the need for separate ingest notebooks per source —
# one notebook handles everything driven by configuration rows.
#
# For each active source ordered by priority:
#   - If source_type == 'table': JDBC read with optional watermark filter
#   - If source_type == 'file': Parquet read from Files/ path
#   - Apply _ingested_at, _source_name metadata columns
#   - Write to target Delta table (overwrite for full, append for incremental/cdc)
#   - Update last_load_timestamp and last_load_rows in metadata table
#
# Parameters (set via pipeline or widget defaults):
#   schedule_filter — only ingest sources matching this schedule ('daily', 'hourly', 'weekly', 'all')

from pyspark.sql.functions import col, current_timestamp, lit
from datetime import datetime

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
# When called from a Fabric pipeline the parameter is injected automatically;
# the widget default keeps the notebook runnable interactively.
try:
    schedule_filter = str(
        dbutils.widgets.get("schedule_filter")  # type: ignore[name-defined]
    )
except Exception:
    schedule_filter = "daily"

# ---------------------------------------------------------------------------
# Configuration — JDBC connection to the operational SQL Database
# ---------------------------------------------------------------------------
SQLDB_JDBC_URL = (
    "jdbc:sqlserver://<your-sqldb-endpoint>.database.fabric.microsoft.com:1433;"
    "database=contoso_operational_db;"
    "encrypt=true;"
    "trustServerCertificate=false;"
    "authentication=ActiveDirectoryMSI"
)

JDBC_PROPERTIES = {
    "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "authentication": "ActiveDirectoryMSI",
}


# ---------------------------------------------------------------------------
# Step 1 — Read active pipeline metadata rows
# ---------------------------------------------------------------------------
def load_metadata(spark, jdbc_url, jdbc_props, schedule):
    """Return a list of dicts — one per active source matching the schedule."""
    if schedule == "all":
        where_clause = "is_active = 1"
    else:
        where_clause = f"is_active = 1 AND schedule = '{schedule}'"

    query = f"""
        (SELECT source_name, source_type, source_connection,
                source_object, target_lakehouse, target_table,
                load_type, watermark_column, last_load_timestamp,
                max_rows_per_batch, priority
         FROM dbo.PipelineMetadata
         WHERE {where_clause}
         ORDER BY priority ASC) AS metadata
    """
    df = spark.read.jdbc(url=jdbc_url, table=query, properties=jdbc_props)
    return [row.asDict() for row in df.collect()]


# ---------------------------------------------------------------------------
# Step 2 — Source-type handlers
# ---------------------------------------------------------------------------
def ingest_table_source(spark, meta, jdbc_url, jdbc_props):
    """JDBC read from an OLTP table with optional watermark-based filtering."""
    source_object = meta["source_object"]
    watermark_col = meta["watermark_column"]
    last_ts = meta["last_load_timestamp"]
    max_rows = meta["max_rows_per_batch"]

    # Build the source query — incremental if we have a watermark
    if watermark_col and last_ts and meta["load_type"] in ("incremental", "cdc"):
        query = (
            f"(SELECT TOP {max_rows} * FROM {source_object} "
            f"WHERE {watermark_col} > '{last_ts}' "
            f"ORDER BY {watermark_col} ASC) AS src"
        )
    else:
        # Full extract
        query = f"(SELECT * FROM {source_object}) AS src"

    return spark.read.jdbc(url=jdbc_url, table=query, properties=jdbc_props)


def ingest_file_source(spark, meta):
    """Read parquet from the lakehouse Files/ path."""
    source_path = meta["source_object"]
    return spark.read.parquet(source_path)


# ---------------------------------------------------------------------------
# Step 3 — Write to bronze Delta table
# ---------------------------------------------------------------------------
def write_bronze(df, meta):
    """Write the DataFrame to the target Delta table with ingestion metadata."""
    df = (
        df
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_name", lit(meta["source_name"]))
    )

    target_table = meta["target_table"]
    load_type = meta["load_type"]

    if load_type == "full":
        df.write.format("delta").mode("overwrite").saveAsTable(target_table)
    else:
        # incremental / cdc → append new rows
        df.write.format("delta").mode("append").saveAsTable(target_table)

    return df.count()


# ---------------------------------------------------------------------------
# Step 4 — Update metadata table after successful load
# ---------------------------------------------------------------------------
def update_metadata(spark, jdbc_url, source_name, rows_loaded):
    """Set last_load_timestamp and last_load_rows for the source."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    update_sql = f"""
        UPDATE dbo.PipelineMetadata
        SET last_load_timestamp = '{now}',
            last_load_rows      = {rows_loaded},
            updated_at          = '{now}'
        WHERE source_name = '{source_name}'
    """
    from py4j.java_gateway import java_import

    java_import(spark._jvm, "java.sql.DriverManager")
    conn = spark._jvm.java.sql.DriverManager.getConnection(jdbc_url)
    try:
        stmt = conn.createStatement()
        stmt.executeUpdate(update_sql)
        stmt.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main — orchestrate ingestion for every active source
# ---------------------------------------------------------------------------
print("=" * 70)
print("Metadata-Driven Bronze Ingestion")
print(f"Schedule filter: {schedule_filter}")
print("=" * 70)

sources = load_metadata(spark, SQLDB_JDBC_URL, JDBC_PROPERTIES, schedule_filter)
print(f"Found {len(sources)} active source(s) to ingest.\n")

results = []

for meta in sources:
    name = meta["source_name"]
    src_type = meta["source_type"]
    target = meta["target_table"]
    print(f"--- [{meta['priority']:03d}] {name} ({src_type}) → {target} ---")

    try:
        # Dispatch by source type
        if src_type == "table":
            df = ingest_table_source(spark, meta, SQLDB_JDBC_URL, JDBC_PROPERTIES)
        elif src_type == "file":
            df = ingest_file_source(spark, meta)
        else:
            print(f"  ⚠ Unsupported source_type '{src_type}', skipping.")
            results.append((name, 0, "skipped"))
            continue

        row_count = df.count()
        if row_count == 0:
            print("  No new rows to ingest.")
            results.append((name, 0, "no_data"))
            continue

        # Write to bronze
        written = write_bronze(df, meta)
        print(f"  Wrote {written:,} rows to {target} ({meta['load_type']})")

        # Update metadata watermark
        update_metadata(spark, SQLDB_JDBC_URL, name, written)
        results.append((name, written, "success"))

    except Exception as exc:
        print(f"  ✗ FAILED: {exc}")
        results.append((name, 0, "error"))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Ingestion Summary")
print("=" * 70)
for name, rows, status in results:
    print(f"  {name:30s}  {rows:>10,} rows  [{status}]")

total = sum(r for _, r, _ in results)
succeeded = sum(1 for _, _, s in results if s == "success")
failed = sum(1 for _, _, s in results if s == "error")
print(f"\n  Total rows: {total:,}  |  Succeeded: {succeeded}  |  Failed: {failed}")
print("Metadata-driven bronze ingestion complete.")
