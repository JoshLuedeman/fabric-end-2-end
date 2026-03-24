# Fabric notebook source
# Fabric Notebook: Sync Cosmos DB to Lakehouse (Bronze Layer)
#
# Reads data from Fabric Cosmos DB containers (product_catalog, customer_360,
# order_events) using the Cosmos DB Spark connector and writes to the bronze
# Lakehouse as Delta tables. Designed for scheduled runs (every 15 min) or
# manual trigger after bulk data changes.
#
# Prerequisites:
#   - Cosmos DB for NoSQL endpoint available within Fabric workspace
#   - Lakehouse "lh_bronze" attached to this notebook
#   - Spark pool with the azure-cosmos-spark connector (bundled in Fabric)

# COMMAND ----------

# MAGIC %md
# MAGIC # Cosmos DB → Lakehouse Bronze Sync
# MAGIC
# MAGIC This notebook syncs operational NoSQL data from Fabric Cosmos DB into the
# MAGIC bronze Lakehouse layer as Delta tables. It uses the **Azure Cosmos DB Spark
# MAGIC connector** (OLTP) with change feed for incremental reads.
# MAGIC
# MAGIC | Container | Bronze Table | Partition Key | Strategy |
# MAGIC |-----------|-------------|---------------|----------|
# MAGIC | product_catalog | bronze_cosmos_product_catalog | /category/l1 | Full refresh (small dataset) |
# MAGIC | customer_360 | bronze_cosmos_customer_360 | /loyalty_tier | Incremental (change feed) |
# MAGIC | order_events | bronze_cosmos_order_events | /order_id | Incremental (change feed) |

# COMMAND ----------

from pyspark.sql.functions import col, current_timestamp, lit, explode, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, ArrayType, MapType
from datetime import datetime

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Cosmos DB connection settings
# In Fabric, the Cosmos DB endpoint is accessible via workspace-level credentials.
# No secrets are stored in the notebook — authentication is via Entra ID (MSI).
COSMOS_CONFIG = {
    "spark.cosmos.accountEndpoint": "<your-cosmos-endpoint>.documents.fabric.microsoft.com",
    "spark.cosmos.accountKey": "",  # Leave empty — Fabric uses managed identity
    "spark.cosmos.useGatewayMode": "true",
    "spark.cosmos.database": "contoso_cosmosdb",
    "spark.cosmos.preferredRegionsList": "East US",
    "spark.cosmos.read.inferSchema.enabled": "true",
    "spark.cosmos.read.inferSchema.includeSystemProperties": "false",
}

# Container-to-table mapping with sync strategy
SYNC_CONFIG = [
    {
        "container": "product_catalog",
        "bronze_table": "bronze_cosmos_product_catalog",
        "strategy": "full",  # Full overwrite — catalog is ~50K docs
        "description": "Product catalog with rich attributes, pricing, and reviews",
    },
    {
        "container": "customer_360",
        "bronze_table": "bronze_cosmos_customer_360",
        "strategy": "incremental",  # Change feed — 2M+ customer profiles
        "description": "Customer 360 profiles with demographics, purchase history, and recommendations",
    },
    {
        "container": "order_events",
        "bronze_table": "bronze_cosmos_order_events",
        "strategy": "incremental",  # Change feed — high volume event stream
        "description": "Order lifecycle events (placed, confirmed, shipped, delivered, etc.)",
    },
]

# Bronze lakehouse path
BRONZE_LAKEHOUSE = "abfss://lh_bronze@onelake.dfs.fabric.microsoft.com"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Helper Functions

# COMMAND ----------

def read_cosmos_full(spark, cosmos_config, container_name):
    """Read all documents from a Cosmos DB container (full extract)."""
    config = {
        **cosmos_config,
        "spark.cosmos.container": container_name,
        "spark.cosmos.read.partitioning.strategy": "Default",
    }

    df = (
        spark.read
        .format("cosmos.oltp")
        .options(**config)
        .load()
    )

    # Add ingestion metadata
    df = (
        df
        .withColumn("_bronze_ingested_at", current_timestamp())
        .withColumn("_bronze_source", lit(f"cosmos.{container_name}"))
        .withColumn("_bronze_strategy", lit("full"))
    )

    return df


def read_cosmos_incremental(spark, cosmos_config, container_name, checkpoint_path):
    """Read changes from a Cosmos DB container using the change feed."""
    config = {
        **cosmos_config,
        "spark.cosmos.container": container_name,
        "spark.cosmos.changeFeed.startFrom": "Beginning",
        "spark.cosmos.changeFeed.mode": "Incremental",
        "spark.cosmos.changeFeed.itemCountPerTriggerHint": "10000",
        "spark.cosmos.read.partitioning.strategy": "Default",
    }

    df = (
        spark.read
        .format("cosmos.oltp.changeFeed")
        .options(**config)
        .load()
    )

    # Add ingestion metadata
    df = (
        df
        .withColumn("_bronze_ingested_at", current_timestamp())
        .withColumn("_bronze_source", lit(f"cosmos.{container_name}"))
        .withColumn("_bronze_strategy", lit("incremental"))
    )

    return df

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sync Execution

# COMMAND ----------

sync_start = datetime.utcnow()
sync_results = []

print(f"=== Cosmos DB → Bronze Sync Started: {sync_start.isoformat()}Z ===\n")

for config in SYNC_CONFIG:
    container = config["container"]
    bronze_table = config["bronze_table"]
    strategy = config["strategy"]
    target_path = f"{BRONZE_LAKEHOUSE}/Tables/{bronze_table}"
    checkpoint_path = f"{BRONZE_LAKEHOUSE}/Files/_checkpoints/cosmos/{container}"

    print(f"▸ Syncing: {container} → {bronze_table} (strategy: {strategy})")

    try:
        if strategy == "full":
            # Full overwrite — read all, write with overwrite mode
            df = read_cosmos_full(spark, COSMOS_CONFIG, container)
            row_count = df.count()

            (
                df.write
                .format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .save(target_path)
            )

            print(f"  ✓ Full sync complete: {row_count:,} documents written")

        elif strategy == "incremental":
            # Incremental — use change feed, merge into existing table
            df = read_cosmos_incremental(spark, COSMOS_CONFIG, container, checkpoint_path)
            row_count = df.count()

            if row_count > 0:
                # Write as append — downstream silver layer handles dedup/merge
                (
                    df.write
                    .format("delta")
                    .mode("append")
                    .option("mergeSchema", "true")
                    .save(target_path)
                )
                print(f"  ✓ Incremental sync complete: {row_count:,} changed documents appended")
            else:
                print(f"  ○ No changes detected since last sync")
                row_count = 0

        sync_results.append({
            "container": container,
            "table": bronze_table,
            "strategy": strategy,
            "rows": row_count,
            "status": "success",
        })

    except Exception as e:
        print(f"  ✗ ERROR syncing {container}: {str(e)}")
        sync_results.append({
            "container": container,
            "table": bronze_table,
            "strategy": strategy,
            "rows": 0,
            "status": f"error: {str(e)[:200]}",
        })

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sync Summary

# COMMAND ----------

sync_end = datetime.utcnow()
duration = (sync_end - sync_start).total_seconds()

print(f"\n=== Cosmos DB → Bronze Sync Summary ===")
print(f"Duration: {duration:.1f}s")
print(f"{'Container':<25} {'Table':<40} {'Strategy':<12} {'Rows':>10} {'Status'}")
print("-" * 110)

total_rows = 0
for r in sync_results:
    total_rows += r["rows"]
    print(f"{r['container']:<25} {r['table']:<40} {r['strategy']:<12} {r['rows']:>10,} {r['status']}")

print("-" * 110)
print(f"{'TOTAL':<79} {total_rows:>10,}")

# Write sync log to bronze for lineage tracking
sync_log_df = spark.createDataFrame(sync_results)
sync_log_df = (
    sync_log_df
    .withColumn("sync_timestamp", lit(sync_start.isoformat() + "Z"))
    .withColumn("duration_seconds", lit(duration))
)
sync_log_df.write.format("delta").mode("append").save(
    f"{BRONZE_LAKEHOUSE}/Tables/_sync_log_cosmos"
)
print(f"\nSync log appended to _sync_log_cosmos")
