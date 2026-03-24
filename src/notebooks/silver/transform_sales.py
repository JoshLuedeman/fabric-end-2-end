# Fabric Notebook: Silver – Transform Sales Transactions
# Reads bronze_sales_transactions, applies quality filters, standardization,
# derived calculations, deduplication, and writes silver_sales_transactions.

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ──────────────────────────────────────────────
# 1. Read bronze
# ──────────────────────────────────────────────
print("Reading bronze_sales_transactions...")
df_raw = spark.read.format("delta").table("bronze_sales_transactions")
total_read = df_raw.count()
print(f"  Total rows read: {total_read}")

# ──────────────────────────────────────────────
# 2. Data-quality filters
# ──────────────────────────────────────────────
df_clean = (
    df_raw
    .filter(col("customer_id").isNotNull())
    .filter(col("product_id").isNotNull())
    .filter(col("quantity") > 0)
    .filter(col("unit_price") > 0)
)
filtered_out = total_read - df_clean.count()
print(f"  Rows filtered out (null keys / invalid qty/price): {filtered_out}")

# ──────────────────────────────────────────────
# 3. Standardise string columns
# ──────────────────────────────────────────────
df_std = (
    df_clean
    .withColumn("payment_method", initcap(lower(trim(col("payment_method")))))
    .withColumn("channel", initcap(lower(trim(col("channel")))))
)

# ──────────────────────────────────────────────
# 4. Derived financial columns
# ──────────────────────────────────────────────
TAX_RATE = 0.08

df_calc = (
    df_std
    .withColumn("gross_amount", col("quantity") * col("unit_price"))
    .withColumn("discount_amount",
                (col("quantity") * col("unit_price")) * (col("discount_pct") / lit(100)))
    .withColumn("net_amount",
                (col("quantity") * col("unit_price"))
                - (col("quantity") * col("unit_price")) * (col("discount_pct") / lit(100)))
    .withColumn("tax_amount",
                ((col("quantity") * col("unit_price"))
                 - (col("quantity") * col("unit_price")) * (col("discount_pct") / lit(100)))
                * lit(TAX_RATE))
    .withColumn("total_with_tax",
                ((col("quantity") * col("unit_price"))
                 - (col("quantity") * col("unit_price")) * (col("discount_pct") / lit(100)))
                * (lit(1) + lit(TAX_RATE)))
)

# ──────────────────────────────────────────────
# 5. Deduplicate by transaction_id (keep first)
# ──────────────────────────────────────────────
window_dedup = Window.partitionBy("transaction_id").orderBy("transaction_date")
df_dedup = (
    df_calc
    .withColumn("_row_num", row_number().over(window_dedup))
    .filter(col("_row_num") == 1)
    .drop("_row_num")
)

# ──────────────────────────────────────────────
# 6. Add processing metadata
# ──────────────────────────────────────────────
df_final = df_dedup.withColumn("_processed_at", current_timestamp())

# ──────────────────────────────────────────────
# 7. Write silver table
# ──────────────────────────────────────────────
df_final.write.format("delta").mode("overwrite").saveAsTable("silver_sales_transactions")
final_count = df_final.count()

print(f"\n=== Sales Transaction Summary ===")
print(f"  Total read:       {total_read}")
print(f"  Filtered out:     {filtered_out}")
print(f"  Final written:    {final_count}")
print("Silver sales transformation complete.")
