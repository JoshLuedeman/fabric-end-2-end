# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — dim_store
# MAGIC Builds the store dimension (SCD Type 1 — full overwrite).

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Read silver layer
# ---------------------------------------------------------------------------
df_silver = spark.read.format("delta").table("silver_stores")

# ---------------------------------------------------------------------------
# 2. Build dimension
# ---------------------------------------------------------------------------
df_dim = (
    df_silver
    .withColumn("store_sk", monotonically_increasing_id() + 1)
    .select(
        col("store_sk"),
        col("store_id"),
        col("store_name"),
        col("store_type"),
        col("city"),
        col("state"),
        col("country"),
        col("region"),
        col("latitude"),
        col("longitude"),
        col("square_footage"),
        col("opening_date"),
        current_date().alias("effective_date"),
        lit(True).alias("is_current"),
    )
)

# ---------------------------------------------------------------------------
# 3. Write to gold (overwrite — SCD Type 1)
# ---------------------------------------------------------------------------
(
    df_dim
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("dim_store")
)

print("✅ dim_store written successfully.")
