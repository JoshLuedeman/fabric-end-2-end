# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — fact_sales
# MAGIC Builds the sales fact table by joining silver transactions with dimension
# MAGIC tables to resolve surrogate keys.

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Read source tables
# ---------------------------------------------------------------------------
df_silver = spark.read.format("delta").table("silver_sales_transactions")

df_dim_customer = (
    spark.read.format("delta").table("dim_customer")
    .filter(col("is_current") == True)
    .select("customer_sk", "customer_id")
)

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
    .join(df_dim_customer, on="customer_id", how="left")
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
        date_format(col("transaction_date"), "yyyyMMdd").cast("int"),
    )
    .withColumn("sale_sk", monotonically_increasing_id() + 1)
    .select(
        col("sale_sk"),
        col("date_key"),
        col("customer_sk"),
        col("product_sk"),
        col("store_sk"),
        col("transaction_id"),
        col("quantity"),
        col("unit_price"),
        col("discount_pct"),
        col("gross_amount"),
        col("net_amount"),
        col("tax_amount"),
        col("total_with_tax").alias("total_amount"),
        col("payment_method"),
        col("channel"),
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
    .saveAsTable("fact_sales")
)

print("✅ fact_sales written successfully.")
