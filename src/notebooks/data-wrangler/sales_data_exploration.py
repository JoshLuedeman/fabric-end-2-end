# Fabric notebook source
# MAGIC %md
# MAGIC # Data Wrangler — Sales Data Exploration & Cleaning
# MAGIC
# MAGIC **Purpose:** Profile sales transaction data, apply common transformations
# MAGIC (handle nulls, normalise amounts, derive time features), and save
# MAGIC the cleaned dataset to the silver layer.
# MAGIC
# MAGIC **Business Context:** Raw sales data ingested into the bronze Lakehouse
# MAGIC contains quality issues — null amounts, inconsistent currency codes,
# MAGIC missing timestamps, and duplicate transactions from POS retries. This
# MAGIC notebook applies Data Wrangler-style transformations to produce a clean
# MAGIC silver-layer dataset ready for aggregation into gold fact tables.
# MAGIC
# MAGIC **Data Wrangler Pattern:** Each transformation section shows the
# MAGIC "code generation" pattern where Fabric Data Wrangler auto-generates
# MAGIC PySpark code from visual operations. The generated code is marked with
# MAGIC `# ---- Data Wrangler Generated Code ----` headers.
# MAGIC
# MAGIC **Data Source:** `lh_bronze.raw_sales` (bronze Lakehouse)
# MAGIC
# MAGIC **Output:** `lh_silver.cleaned_sales` (silver Lakehouse)

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

from pyspark.sql.functions import (
    col, count as _count, countDistinct, sum as _sum, avg as _avg,
    stddev, min as _min, max as _max, when, isnan, isnull, lit,
    current_timestamp, year, month, dayofweek, dayofmonth, hour,
    quarter, weekofyear, date_format, to_date, to_timestamp,
    coalesce, trim, upper, lower, round as _round, row_number,
    regexp_replace, length, abs as _abs, expr,
)
from pyspark.sql.window import Window
from pyspark.sql.types import DoubleType, IntegerType, TimestampType

import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BRONZE_TABLE = "raw_sales"
SILVER_TABLE = "cleaned_sales"
DEFAULT_CURRENCY = "USD"
DEFAULT_TAX_RATE = 0.08

print("Imports and configuration loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load Bronze Sales Data

# COMMAND ----------

print(f"Reading bronze layer: {BRONZE_TABLE}...")

try:
    df = spark.read.format("delta").table(BRONZE_TABLE)
except Exception:
    # Fall back to fact_sales if raw_sales doesn't exist
    print(f"  ⚠ {BRONZE_TABLE} not found, trying fact_sales...")
    df = spark.read.format("delta").table("fact_sales")

total_rows = df.count()
total_cols = len(df.columns)

print(f"✅ Loaded: {total_rows:,} rows × {total_cols} columns")
print(f"\nSchema:")
df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Data Profiling Summary
# MAGIC
# MAGIC *Data Wrangler Generated — Dataset Overview*
# MAGIC
# MAGIC Quick profiling to understand data quality before transformations.

# COMMAND ----------

print("Profiling sales data...\n")

# Row-level stats
print(f"  Total rows:    {total_rows:,}")
print(f"  Total columns: {total_cols}")

# Column-level null analysis
print(f"\n  Column Null Analysis:")
for field in df.schema.fields:
    col_name = field.name
    null_count = df.filter(isnull(col(col_name))).count()
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    flag = "🟢" if null_pct < 1 else ("🟡" if null_pct < 5 else "🔴")
    print(f"    {flag} {col_name}: {null_count:,} nulls ({null_pct:.1f}%)")

# Numeric column distributions
print(f"\n  Numeric Distributions:")
numeric_cols = [
    f.name for f in df.schema.fields
    if f.dataType.typeName() in ("integer", "long", "double", "float")
    and not f.name.endswith("_sk") and not f.name.endswith("_id")
]

for col_name in numeric_cols[:8]:
    stats = df.agg(
        _min(col(col_name)).alias("min"),
        _max(col(col_name)).alias("max"),
        _avg(col(col_name)).alias("mean"),
        stddev(col(col_name)).alias("std"),
    ).collect()[0]
    print(f"    {col_name}: min={stats['min']}, max={stats['max']}, "
          f"mean={stats['mean']:.2f}, std={stats['std']:.2f}" if stats['std'] else
          f"    {col_name}: min={stats['min']}, max={stats['max']}")

print(f"\n✅ Profiling complete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Handle Null Values
# MAGIC
# MAGIC *Data Wrangler Generated — Fill/Drop Nulls*

# COMMAND ----------

# ---- Data Wrangler Generated Code ----
# Operation: Fill null transaction amounts with 0.0
df = df.withColumn(
    "total_amount",
    when(col("total_amount").isNull(), lit(0.0)).otherwise(col("total_amount"))
)

# ---- Data Wrangler Generated Code ----
# Operation: Fill null quantity with 1 (single-item default)
if "quantity" in df.columns:
    df = df.withColumn(
        "quantity",
        when(col("quantity").isNull(), lit(1)).otherwise(col("quantity"))
    )

# ---- Data Wrangler Generated Code ----
# Operation: Fill null unit_price from total_amount / quantity
if "unit_price" in df.columns and "quantity" in df.columns:
    df = df.withColumn(
        "unit_price",
        when(
            col("unit_price").isNull() & (col("quantity") > 0),
            _round(col("total_amount") / col("quantity"), 2)
        ).otherwise(col("unit_price"))
    )

# ---- Data Wrangler Generated Code ----
# Operation: Fill null currency_code with default
if "currency_code" in df.columns:
    df = df.withColumn(
        "currency_code",
        when(col("currency_code").isNull(), lit(DEFAULT_CURRENCY))
        .otherwise(upper(trim(col("currency_code"))))
    )

# ---- Data Wrangler Generated Code ----
# Operation: Drop rows where sale_date is null (cannot process without date)
if "sale_date" in df.columns:
    before = df.count()
    df = df.filter(col("sale_date").isNotNull())
    after = df.count()
    dropped = before - after
    print(f"  Dropped {dropped:,} rows with null sale_date")

print(f"✅ Null handling complete. Rows remaining: {df.count():,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Normalise Amounts
# MAGIC
# MAGIC *Data Wrangler Generated — Standardise Numeric Columns*

# COMMAND ----------

# ---- Data Wrangler Generated Code ----
# Operation: Ensure total_amount is non-negative (absolute value for refund corrections)
df = df.withColumn(
    "total_amount_normalised",
    when(col("total_amount") < 0, _abs(col("total_amount")))
    .otherwise(col("total_amount"))
)

# ---- Data Wrangler Generated Code ----
# Operation: Round monetary columns to 2 decimal places
df = df.withColumn(
    "total_amount_normalised",
    _round(col("total_amount_normalised"), 2)
)

# ---- Data Wrangler Generated Code ----
# Operation: Calculate tax_amount if not present
if "tax_amount" not in df.columns:
    df = df.withColumn(
        "tax_amount",
        _round(col("total_amount_normalised") * lit(DEFAULT_TAX_RATE), 2)
    )

# ---- Data Wrangler Generated Code ----
# Operation: Calculate net_amount (total - tax)
df = df.withColumn(
    "net_amount",
    _round(col("total_amount_normalised") - col("tax_amount"), 2)
)

# Remove outlier transactions (> $50,000 single transaction for retail)
AMOUNT_CAP = 50000.0
outlier_count = df.filter(col("total_amount_normalised") > AMOUNT_CAP).count()
if outlier_count > 0:
    print(f"  ⚠ Capping {outlier_count:,} transactions above ${AMOUNT_CAP:,.0f}")
    df = df.withColumn(
        "total_amount_normalised",
        when(col("total_amount_normalised") > lit(AMOUNT_CAP), lit(AMOUNT_CAP))
        .otherwise(col("total_amount_normalised"))
    )

print(f"✅ Amount normalisation complete.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Derive Time Features
# MAGIC
# MAGIC *Data Wrangler Generated — Date/Time Feature Engineering*
# MAGIC
# MAGIC Extract temporal features from the sale_date column for downstream
# MAGIC analytics and ML models.

# COMMAND ----------

# ---- Data Wrangler Generated Code ----
# Operation: Extract year from sale_date
df = df.withColumn("sale_year", year(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Extract month from sale_date
df = df.withColumn("sale_month", month(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Extract quarter from sale_date
df = df.withColumn("sale_quarter", quarter(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Extract day of week (1=Sunday, 7=Saturday)
df = df.withColumn("sale_day_of_week", dayofweek(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Extract day of month
df = df.withColumn("sale_day_of_month", dayofmonth(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Extract week of year
df = df.withColumn("sale_week_of_year", weekofyear(col("sale_date")))

# ---- Data Wrangler Generated Code ----
# Operation: Derive is_weekend flag
df = df.withColumn(
    "is_weekend",
    when(col("sale_day_of_week").isin(1, 7), lit(True)).otherwise(lit(False))
)

# ---- Data Wrangler Generated Code ----
# Operation: Derive day_period (Morning/Afternoon/Evening/Night)
if "sale_timestamp" in df.columns or "sale_time" in df.columns:
    time_col = "sale_timestamp" if "sale_timestamp" in df.columns else "sale_time"
    df = df.withColumn("sale_hour", hour(col(time_col)))
    df = df.withColumn(
        "day_period",
        when(col("sale_hour").between(6, 11), lit("Morning"))
        .when(col("sale_hour").between(12, 17), lit("Afternoon"))
        .when(col("sale_hour").between(18, 21), lit("Evening"))
        .otherwise(lit("Night"))
    )

# ---- Data Wrangler Generated Code ----
# Operation: Derive fiscal_quarter (Tales & Timber fiscal year starts April)
df = df.withColumn(
    "fiscal_quarter",
    when(col("sale_month").between(4, 6), lit("Q1"))
    .when(col("sale_month").between(7, 9), lit("Q2"))
    .when(col("sale_month").between(10, 12), lit("Q3"))
    .otherwise(lit("Q4"))
)

print(f"✅ Time features derived. New columns added:")
time_cols = ["sale_year", "sale_month", "sale_quarter", "sale_day_of_week",
             "sale_day_of_month", "sale_week_of_year", "is_weekend", "fiscal_quarter"]
for tc in time_cols:
    print(f"   • {tc}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Remove Duplicates
# MAGIC
# MAGIC *Data Wrangler Generated — Deduplicate Rows*
# MAGIC
# MAGIC POS systems can send duplicate transactions during network retries.
# MAGIC Remove exact duplicates and near-duplicates (same store, customer,
# MAGIC amount within 1 minute).

# COMMAND ----------

before_dedup = df.count()

# ---- Data Wrangler Generated Code ----
# Operation: Drop exact duplicate rows
df = df.dropDuplicates()

after_exact_dedup = df.count()
exact_dups = before_dedup - after_exact_dedup
print(f"  Removed {exact_dups:,} exact duplicate rows")

# ---- Data Wrangler Generated Code ----
# Operation: Remove near-duplicate transactions (same store + customer + amount + date)
dedup_cols = [c for c in ["store_sk", "customer_sk", "total_amount", "sale_date"]
              if c in df.columns]

if len(dedup_cols) >= 3:
    window = Window.partitionBy(dedup_cols).orderBy(col("sale_date").asc())
    df = df.withColumn("_dedup_row", row_number().over(window))
    near_dups = df.filter(col("_dedup_row") > 1).count()
    df = df.filter(col("_dedup_row") == 1).drop("_dedup_row")
    print(f"  Removed {near_dups:,} near-duplicate rows")

after_dedup = df.count()
total_removed = before_dedup - after_dedup
print(f"\n✅ Deduplication complete. Removed {total_removed:,} rows total.")
print(f"   Before: {before_dedup:,} → After: {after_dedup:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Add Metadata Columns

# COMMAND ----------

# ---- Data Wrangler Generated Code ----
# Operation: Add processing metadata
df = (
    df
    .withColumn("_processed_at", current_timestamp())
    .withColumn("_source_table", lit(BRONZE_TABLE))
    .withColumn("_processing_notebook", lit("sales_data_exploration"))
)

print(f"✅ Metadata columns added: _processed_at, _source_table, _processing_notebook")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Write Cleaned Data to Silver Layer

# COMMAND ----------

print(f"Writing cleaned data to silver layer: {SILVER_TABLE}...")

(
    df
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(SILVER_TABLE)
)

final_count = df.count()
final_cols = len(df.columns)

print(f"✅ {SILVER_TABLE} written successfully!")
print(f"   Rows:    {final_count:,}")
print(f"   Columns: {final_cols}")
print(f"   Format:  Delta (silver Lakehouse)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Post-Write Validation

# COMMAND ----------

# Verify the written data
df_verify = spark.read.format("delta").table(SILVER_TABLE)
verify_count = df_verify.count()
assert verify_count == final_count, f"Row count mismatch: expected {final_count}, got {verify_count}"

# Check no nulls in critical columns
critical_cols = [c for c in ["sale_date", "total_amount_normalised"] if c in df_verify.columns]
for cc in critical_cols:
    null_count = df_verify.filter(col(cc).isNull()).count()
    assert null_count == 0, f"Critical column {cc} has {null_count} nulls after cleaning"

print(f"✅ Post-write validation passed.")
print(f"   Row count verified: {verify_count:,}")
print(f"   No nulls in critical columns: {', '.join(critical_cols)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Summary
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Source table | `raw_sales` (bronze Lakehouse) |
# MAGIC | Output table | `cleaned_sales` (silver Lakehouse) |
# MAGIC | Transformations applied | Null handling, amount normalisation, time features, dedup |
# MAGIC | Columns added | sale_year, sale_month, sale_quarter, sale_day_of_week, is_weekend, fiscal_quarter, net_amount, tax_amount |
# MAGIC | Data Wrangler patterns | 15+ auto-generated transformation blocks |
# MAGIC | Quality checks | Post-write row count + null validation |

print("Sales data exploration and cleaning notebook complete.")
