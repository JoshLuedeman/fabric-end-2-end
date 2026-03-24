# Fabric Notebook: Ingest from Fabric SQL Database (OLTP → Bronze)
# Connects to the operational SQL Database via JDBC, reads CDC watermarks
# to pull incremental changes, and writes them as Delta tables in the
# bronze Lakehouse. This is the "OLTP → Analytics" bridge.
#
# Tracked tables: Customers, Products, Stores, Transactions,
#                 TransactionItems, Inventory, CustomerInteractions, Promotions

from pyspark.sql.functions import col, current_timestamp, lit
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Fabric SQL Database JDBC connection
# In Fabric, the SQL Database endpoint is accessible via the workspace connection.
# The connection string is injected via Fabric-managed JDBC; no secrets needed.
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

# Tables to extract via CDC
CDC_TABLES = [
    "Customers",
    "Products",
    "Stores",
    "Transactions",
    "TransactionItems",
    "Inventory",
    "CustomerInteractions",
    "Promotions",
]

# Mapping from OLTP table name → bronze Delta table name
BRONZE_TABLE_MAP = {
    "Customers":            "bronze_sqldb_customers",
    "Products":             "bronze_sqldb_products",
    "Stores":               "bronze_sqldb_stores",
    "Transactions":         "bronze_sqldb_transactions",
    "TransactionItems":     "bronze_sqldb_transaction_items",
    "Inventory":            "bronze_sqldb_inventory",
    "CustomerInteractions": "bronze_sqldb_customer_interactions",
    "Promotions":           "bronze_sqldb_promotions",
}


# ---------------------------------------------------------------------------
# Helper: Read CDC watermark for a given table
# ---------------------------------------------------------------------------
def get_watermark(spark, jdbc_url, table_name, jdbc_props):
    """Read the last_extracted_at watermark for a table from the OLTP database."""
    query = f"""
        (SELECT table_name, last_extracted_at, rows_extracted
         FROM dbo.CDC_Watermarks
         WHERE table_name = '{table_name}') AS watermark
    """
    df = spark.read.jdbc(url=jdbc_url, table=query, properties=jdbc_props)
    row = df.collect()
    if row:
        return row[0]["last_extracted_at"]
    return None


# ---------------------------------------------------------------------------
# Helper: Extract changed rows since the watermark
# ---------------------------------------------------------------------------
def extract_incremental(spark, jdbc_url, table_name, watermark, jdbc_props):
    """Pull rows modified after the watermark timestamp."""

    # Build the WHERE clause based on the table's timestamp column
    timestamp_col_map = {
        "Customers":            "updated_at",
        "Products":             "updated_at",
        "Stores":               "store_id",        # Stores: full extract (no updated_at)
        "Transactions":         "transaction_date",
        "TransactionItems":     "transaction_id",   # Joined via Transactions
        "Inventory":            "updated_at",
        "CustomerInteractions": "created_at",
        "Promotions":           "promo_id",         # Small table: full extract
    }

    # For tables with proper timestamp columns, do incremental extract
    if table_name in ("Customers", "Products", "Inventory"):
        ts_col = timestamp_col_map[table_name]
        query = f"(SELECT * FROM dbo.{table_name} WHERE {ts_col} > '{watermark}') AS delta"
    elif table_name == "Transactions":
        query = f"(SELECT * FROM dbo.Transactions WHERE transaction_date > '{watermark}') AS delta"
    elif table_name == "TransactionItems":
        query = f"""
            (SELECT ti.*
             FROM dbo.TransactionItems ti
             INNER JOIN dbo.Transactions t ON ti.transaction_id = t.transaction_id
             WHERE t.transaction_date > '{watermark}') AS delta
        """
    elif table_name == "CustomerInteractions":
        query = f"(SELECT * FROM dbo.CustomerInteractions WHERE created_at > '{watermark}') AS delta"
    else:
        # Full extract for small/reference tables (Stores, Promotions)
        query = f"(SELECT * FROM dbo.{table_name}) AS delta"

    return spark.read.jdbc(url=jdbc_url, table=query, properties=jdbc_props)


# ---------------------------------------------------------------------------
# Helper: Update the CDC watermark after successful extraction
# ---------------------------------------------------------------------------
def update_watermark(spark, jdbc_url, table_name, rows_extracted, jdbc_props):
    """Advance the watermark in the OLTP database after extraction."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    update_query = f"""
        UPDATE dbo.CDC_Watermarks
        SET last_extracted_at = '{now}',
            rows_extracted = rows_extracted + {rows_extracted},
            updated_at = '{now}'
        WHERE table_name = '{table_name}'
    """
    # Execute the update via JDBC statement
    from py4j.java_gateway import java_import

    java_import(spark._jvm, "java.sql.DriverManager")
    conn = spark._jvm.java.sql.DriverManager.getConnection(jdbc_url)
    try:
        stmt = conn.createStatement()
        stmt.executeUpdate(update_query)
        stmt.close()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main ingestion loop
# ---------------------------------------------------------------------------
print("=" * 70)
print("OLTP → Bronze Ingestion: Fabric SQL Database CDC Extract")
print("=" * 70)

extraction_summary = []

for table_name in CDC_TABLES:
    bronze_table = BRONZE_TABLE_MAP[table_name]
    print(f"\n--- Extracting: {table_name} → {bronze_table} ---")

    # 1. Read the current watermark
    watermark = get_watermark(spark, SQLDB_JDBC_URL, table_name, JDBC_PROPERTIES)
    if watermark is None:
        print(f"  ⚠ No watermark found for {table_name}, skipping.")
        continue
    print(f"  Last watermark: {watermark}")

    # 2. Extract changed rows since the watermark
    df = extract_incremental(spark, SQLDB_JDBC_URL, table_name, watermark, JDBC_PROPERTIES)

    row_count = df.count()
    if row_count == 0:
        print(f"  No new rows since last extraction.")
        extraction_summary.append((table_name, 0, "no_changes"))
        continue

    print(f"  Extracted {row_count} rows")

    # 3. Add ingestion metadata (matches existing bronze notebook convention)
    df = (
        df
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", lit(f"sqldb:dbo.{table_name}"))
        .withColumn("_cdc_watermark", lit(str(watermark)))
    )

    # 4. Write to bronze Lakehouse as Delta table
    # Use merge/upsert for dimension tables, append for fact tables
    if table_name in ("Transactions", "TransactionItems", "CustomerInteractions"):
        # Fact tables: append new rows (incremental)
        df.write.format("delta").mode("append").saveAsTable(bronze_table)
        print(f"  Appended {row_count} rows to {bronze_table}")
    else:
        # Dimension/reference tables: overwrite (full refresh on changes)
        df.write.format("delta").mode("overwrite").saveAsTable(bronze_table)
        print(f"  Overwrote {bronze_table} with {row_count} rows")

    # 5. Update the watermark in the OLTP database
    update_watermark(spark, SQLDB_JDBC_URL, table_name, row_count, JDBC_PROPERTIES)
    print(f"  Watermark updated for {table_name}")

    extraction_summary.append((table_name, row_count, "success"))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Extraction Summary")
print("=" * 70)
for table, rows, status in extraction_summary:
    print(f"  {table:30s}  {rows:>8,} rows  [{status}]")

total_rows = sum(r for _, r, _ in extraction_summary)
print(f"\n  Total rows extracted: {total_rows:,}")
print("OLTP → Bronze ingestion complete.")
