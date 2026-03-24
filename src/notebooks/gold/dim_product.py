# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — dim_product
# MAGIC Builds the product dimension (SCD Type 1 — full overwrite).

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Read silver layer
# ---------------------------------------------------------------------------
df_silver = spark.read.format("delta").table("silver_products")

# ---------------------------------------------------------------------------
# 2. Build dimension
# ---------------------------------------------------------------------------
df_dim = (
    df_silver
    .withColumn("product_sk", monotonically_increasing_id() + 1)
    .select(
        col("product_sk"),
        col("product_id"),
        col("product_name"),
        col("category"),
        col("subcategory"),
        col("brand"),
        col("unit_cost"),
        col("unit_price"),
        col("margin_pct"),
        col("weight_kg"),
        col("supplier_id"),
        col("is_active"),
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
    .saveAsTable("dim_product")
)

print("✅ dim_product written successfully.")
