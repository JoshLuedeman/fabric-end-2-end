# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — fact_inventory
# MAGIC Builds the inventory fact table by joining silver inventory movements
# MAGIC with product and store dimensions.

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Read source tables
# ---------------------------------------------------------------------------
df_silver = spark.read.format("delta").table("silver_inventory")

df_dim_product = (
    spark.read.format("delta").table("dim_product")
    .filter(col("is_current") == True)
    .select("product_sk", "product_id")
)

df_dim_store = (
    spark.read.format("delta").table("dim_store")
    .filter(col("is_current") == True)
    .select("store_sk", "store_id")
)

# ---------------------------------------------------------------------------
# 2. Join silver with dimensions to resolve surrogate keys
# ---------------------------------------------------------------------------
df_joined = (
    df_silver
    .join(df_dim_product, on="product_id", how="left")
    .join(df_dim_store, on="store_id", how="left")
)

# ---------------------------------------------------------------------------
# 3. Build fact table
# ---------------------------------------------------------------------------
df_fact = (
    df_joined
    .withColumn(
        "date_key",
        date_format(col("movement_date"), "yyyyMMdd").cast("int"),
    )
    .withColumn("inventory_sk", monotonically_increasing_id() + 1)
    .withColumn(
        "is_below_reorder",
        col("on_hand_after") < col("reorder_point"),
    )
    .select(
        col("inventory_sk"),
        col("date_key"),
        col("product_sk"),
        col("store_sk"),
        col("inventory_id"),
        col("movement_type"),
        col("quantity"),
        col("unit_cost"),
        col("on_hand_after"),
        col("reorder_point"),
        col("is_below_reorder"),
    )
)

# ---------------------------------------------------------------------------
# 4. Write to gold
# ---------------------------------------------------------------------------
(
    df_fact
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("fact_inventory")
)

print("✅ fact_inventory written successfully.")
