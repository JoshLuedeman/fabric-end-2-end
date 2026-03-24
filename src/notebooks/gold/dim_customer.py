# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — dim_customer
# MAGIC Builds the customer dimension (SCD Type 1 — full overwrite).

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Read silver layer
# ---------------------------------------------------------------------------
df_silver = spark.read.format("delta").table("silver_customers")

# ---------------------------------------------------------------------------
# 2. Build dimension
# ---------------------------------------------------------------------------
df_dim = (
    df_silver
    .withColumn("customer_sk", monotonically_increasing_id() + 1)
    .select(
        col("customer_sk"),
        col("customer_id"),
        col("first_name"),
        col("last_name"),
        col("email"),
        col("phone"),
        col("city"),
        col("state"),
        col("country"),
        col("postal_code"),
        col("loyalty_tier"),
        col("customer_segment"),
        col("lifetime_value"),
        col("is_active"),
        col("customer_age"),
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
    .saveAsTable("dim_customer")
)

print("✅ dim_customer written successfully.")
