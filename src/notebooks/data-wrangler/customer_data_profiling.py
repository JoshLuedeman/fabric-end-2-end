# Fabric notebook source
# MAGIC %md
# MAGIC # Data Wrangler — Customer Data Profiling
# MAGIC
# MAGIC **Purpose:** Profile customer data quality using Data Wrangler-style
# MAGIC analysis. Generate column-level statistics, identify outliers, duplicates,
# MAGIC and data quality issues, and output a data quality report table.
# MAGIC
# MAGIC **Business Context:** Contoso Global Retail has 2M+ customers across
# MAGIC multiple channels. Ensuring data quality is critical for accurate churn
# MAGIC predictions, customer segmentation, and personalised marketing. This
# MAGIC notebook provides a repeatable profiling pipeline that runs before
# MAGIC any downstream ML or analytics workload.
# MAGIC
# MAGIC **Data Wrangler Integration:** This notebook contains code patterns
# MAGIC that replicate what Fabric Data Wrangler auto-generates when you
# MAGIC use its visual profiling and transformation UI. The code blocks
# MAGIC marked with "Data Wrangler Generated" are the kind of PySpark
# MAGIC transformations that Data Wrangler produces.
# MAGIC
# MAGIC **Data Source:** `dim_customer` (gold Lakehouse)
# MAGIC
# MAGIC **Output:** `dq_customer_profile_report` table in gold Lakehouse

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

from pyspark.sql.functions import (
    col, count as _count, countDistinct, sum as _sum, avg as _avg,
    stddev, min as _min, max as _max, when, isnan, isnull, lit,
    length, regexp_extract, current_timestamp, percent_rank, abs as _abs,
    mean as _mean, round as _round,
)
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StringType, IntegerType, DoubleType, DateType, TimestampType,
)

import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOURCE_TABLE = "dim_customer"
OUTPUT_TABLE = "dq_customer_profile_report"
OUTLIER_ZSCORE_THRESHOLD = 3.0
DUPLICATE_CHECK_COLUMNS = ["customer_id", "email"]

print("Imports and configuration loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load Customer Data

# COMMAND ----------

print(f"Reading {SOURCE_TABLE}...")

df = spark.read.format("delta").table(SOURCE_TABLE)
total_rows = df.count()
total_cols = len(df.columns)

print(f"✅ Loaded {SOURCE_TABLE}: {total_rows:,} rows × {total_cols} columns")
print(f"\nSchema:")
df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Column-Level Profiling Statistics
# MAGIC
# MAGIC *Data Wrangler Generated — Column Statistics*
# MAGIC
# MAGIC This block replicates the profiling view that Data Wrangler shows
# MAGIC when you first load a dataset. It calculates null %, unique %,
# MAGIC and basic distribution metrics for every column.

# COMMAND ----------

profile_results = []

for field in df.schema.fields:
    col_name = field.name
    col_type = field.dataType.typeName()

    # Base metrics: null count & unique count
    stats = df.agg(
        _count(when(isnull(col(col_name)) | isnan(col(col_name)) if col_type in ("double", "float") else isnull(col(col_name)), col_name)).alias("null_count"),
        _count(col(col_name)).alias("non_null_count"),
        countDistinct(col(col_name)).alias("unique_count"),
    ).collect()[0]

    null_count = total_rows - stats["non_null_count"]
    null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    unique_count = stats["unique_count"]
    unique_pct = (unique_count / total_rows * 100) if total_rows > 0 else 0

    col_profile = {
        "column_name": col_name,
        "data_type": col_type,
        "total_rows": total_rows,
        "null_count": null_count,
        "null_pct": round(null_pct, 2),
        "non_null_count": stats["non_null_count"],
        "unique_count": unique_count,
        "unique_pct": round(unique_pct, 2),
    }

    # Numeric columns: min, max, mean, stddev
    if col_type in ("integer", "long", "double", "float", "decimal"):
        num_stats = df.agg(
            _min(col(col_name)).alias("min_val"),
            _max(col(col_name)).alias("max_val"),
            _avg(col(col_name)).alias("mean_val"),
            stddev(col(col_name)).alias("stddev_val"),
        ).collect()[0]

        col_profile["min_value"] = str(num_stats["min_val"])
        col_profile["max_value"] = str(num_stats["max_val"])
        col_profile["mean_value"] = str(round(num_stats["mean_val"], 4)) if num_stats["mean_val"] else None
        col_profile["stddev_value"] = str(round(num_stats["stddev_val"], 4)) if num_stats["stddev_val"] else None
    else:
        col_profile["min_value"] = None
        col_profile["max_value"] = None
        col_profile["mean_value"] = None
        col_profile["stddev_value"] = None

    # String columns: min/max length
    if col_type == "string":
        len_stats = df.filter(col(col_name).isNotNull()).agg(
            _min(length(col(col_name))).alias("min_length"),
            _max(length(col(col_name))).alias("max_length"),
            _avg(length(col(col_name))).alias("avg_length"),
        ).collect()[0]
        col_profile["min_length"] = len_stats["min_length"]
        col_profile["max_length"] = len_stats["max_length"]
        col_profile["avg_length"] = round(len_stats["avg_length"], 1) if len_stats["avg_length"] else None
    else:
        col_profile["min_length"] = None
        col_profile["max_length"] = None
        col_profile["avg_length"] = None

    profile_results.append(col_profile)

    # Print summary
    quality = "🟢" if null_pct < 1 else ("🟡" if null_pct < 5 else "🔴")
    print(f"  {quality} {col_name} ({col_type}): {null_pct:.1f}% null, {unique_count:,} unique ({unique_pct:.1f}%)")

print(f"\n✅ Profiled {len(profile_results)} columns.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Duplicate Detection
# MAGIC
# MAGIC *Data Wrangler Generated — Find Duplicates*
# MAGIC
# MAGIC Checks for duplicate records based on business key columns.

# COMMAND ----------

print("Checking for duplicates...")

for dup_col in DUPLICATE_CHECK_COLUMNS:
    if dup_col not in df.columns:
        print(f"  ⚠ Column '{dup_col}' not found — skipping.")
        continue

    dup_count = (
        df
        .groupBy(dup_col)
        .agg(_count("*").alias("cnt"))
        .filter(col("cnt") > 1)
        .count()
    )

    total_dup_rows = (
        df
        .groupBy(dup_col)
        .agg(_count("*").alias("cnt"))
        .filter(col("cnt") > 1)
        .agg(_sum("cnt").alias("total"))
        .collect()[0]["total"]
    ) or 0

    flag = "🔴" if dup_count > 0 else "🟢"
    print(f"  {flag} {dup_col}: {dup_count:,} duplicate values ({total_dup_rows:,} total rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Outlier Detection
# MAGIC
# MAGIC *Data Wrangler Generated — Outlier Identification*
# MAGIC
# MAGIC Identifies outliers using Z-score method on numeric columns.

# COMMAND ----------

print(f"Detecting outliers (Z-score > {OUTLIER_ZSCORE_THRESHOLD})...\n")

outlier_results = []

numeric_cols = [
    f.name for f in df.schema.fields
    if f.dataType.typeName() in ("integer", "long", "double", "float")
    and not f.name.startswith("_")
    and f.name.endswith(("_sk", "_id")) is False
]

# Filter to meaningful numeric columns (exclude surrogate keys)
numeric_cols = [
    c for c in numeric_cols
    if not c.endswith("_sk") and not c.endswith("_id")
]

for col_name in numeric_cols:
    stats = df.agg(
        _avg(col(col_name)).alias("mean_val"),
        stddev(col(col_name)).alias("std_val"),
    ).collect()[0]

    mean_val = stats["mean_val"]
    std_val = stats["std_val"]

    if mean_val is None or std_val is None or std_val == 0:
        continue

    # Count outliers using Z-score
    outlier_count = (
        df
        .filter(col(col_name).isNotNull())
        .filter(
            _abs((col(col_name) - lit(mean_val)) / lit(std_val)) > OUTLIER_ZSCORE_THRESHOLD
        )
        .count()
    )

    outlier_pct = (outlier_count / total_rows * 100) if total_rows > 0 else 0

    outlier_results.append({
        "column_name": col_name,
        "outlier_count": outlier_count,
        "outlier_pct": round(outlier_pct, 2),
        "mean": round(mean_val, 4),
        "stddev": round(std_val, 4),
        "threshold": OUTLIER_ZSCORE_THRESHOLD,
    })

    flag = "🔴" if outlier_pct > 1 else ("🟡" if outlier_count > 0 else "🟢")
    print(f"  {flag} {col_name}: {outlier_count:,} outliers ({outlier_pct:.2f}%)")

print(f"\n✅ Outlier analysis complete for {len(numeric_cols)} numeric columns.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Data Quality Rules Validation
# MAGIC
# MAGIC *Data Wrangler Generated — Custom Validation Rules*
# MAGIC
# MAGIC Business-specific data quality rules for customer data.

# COMMAND ----------

print("Running data quality validation rules...\n")

dq_rules = []

# Rule 1: Email format validation
if "email" in df.columns:
    invalid_emails = df.filter(
        col("email").isNotNull() &
        ~col("email").rlike(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    ).count()
    dq_rules.append({"rule": "Valid email format", "failures": invalid_emails, "severity": "High"})
    flag = "🟢" if invalid_emails == 0 else "🔴"
    print(f"  {flag} Valid email format: {invalid_emails:,} failures")

# Rule 2: Customer ID not null and unique
if "customer_id" in df.columns:
    null_ids = df.filter(col("customer_id").isNull()).count()
    dq_rules.append({"rule": "Customer ID not null", "failures": null_ids, "severity": "Critical"})
    flag = "🟢" if null_ids == 0 else "🔴"
    print(f"  {flag} Customer ID not null: {null_ids:,} failures")

# Rule 3: Loyalty tier in valid set
if "loyalty_tier" in df.columns:
    valid_tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    invalid_tiers = df.filter(
        col("loyalty_tier").isNotNull() &
        ~col("loyalty_tier").isin(valid_tiers)
    ).count()
    dq_rules.append({"rule": "Valid loyalty tier", "failures": invalid_tiers, "severity": "Medium"})
    flag = "🟢" if invalid_tiers == 0 else "🟡"
    print(f"  {flag} Valid loyalty tier: {invalid_tiers:,} failures")

# Rule 4: Lifetime value non-negative
if "lifetime_value" in df.columns:
    negative_ltv = df.filter(col("lifetime_value") < 0).count()
    dq_rules.append({"rule": "Lifetime value non-negative", "failures": negative_ltv, "severity": "High"})
    flag = "🟢" if negative_ltv == 0 else "🔴"
    print(f"  {flag} Lifetime value ≥ 0: {negative_ltv:,} failures")

total_failures = sum(r["failures"] for r in dq_rules)
print(f"\n✅ {len(dq_rules)} rules evaluated. Total failures: {total_failures:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Write Data Quality Report

# COMMAND ----------

# Combine all profiling results into a report table
report_rows = []
for p in profile_results:
    # Find outlier info for this column
    outlier_info = next((o for o in outlier_results if o["column_name"] == p["column_name"]), {})

    report_rows.append({
        "table_name": SOURCE_TABLE,
        "column_name": p["column_name"],
        "data_type": p["data_type"],
        "total_rows": p["total_rows"],
        "null_count": p["null_count"],
        "null_pct": p["null_pct"],
        "unique_count": p["unique_count"],
        "unique_pct": p["unique_pct"],
        "min_value": p.get("min_value"),
        "max_value": p.get("max_value"),
        "mean_value": p.get("mean_value"),
        "stddev_value": p.get("stddev_value"),
        "outlier_count": outlier_info.get("outlier_count", 0),
        "outlier_pct": outlier_info.get("outlier_pct", 0.0),
        "profiled_at": datetime.now().isoformat(),
    })

df_report = spark.createDataFrame(pd.DataFrame(report_rows))
df_report = df_report.withColumn("_created_at", current_timestamp())

(
    df_report
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(OUTPUT_TABLE)
)

print(f"✅ {OUTPUT_TABLE} written: {len(report_rows)} column profiles")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Data Wrangler — Auto-Generated Transformation Code
# MAGIC
# MAGIC The following transformations are examples of what Fabric Data Wrangler
# MAGIC generates when you use its visual UI to clean customer data. These can
# MAGIC be applied to fix the issues identified in the profiling above.

# COMMAND ----------

# ---- Data Wrangler Generated Code ----
# Operation: Fill null values in 'loyalty_tier' with 'Unknown'
def clean_loyalty_tier(df):
    df = df.withColumn(
        "loyalty_tier",
        when(col("loyalty_tier").isNull(), lit("Unknown")).otherwise(col("loyalty_tier"))
    )
    return df

# ---- Data Wrangler Generated Code ----
# Operation: Standardise email to lowercase
def standardise_email(df):
    from pyspark.sql.functions import lower, trim
    df = df.withColumn(
        "email",
        lower(trim(col("email")))
    )
    return df

# ---- Data Wrangler Generated Code ----
# Operation: Remove duplicate customers (keep first occurrence)
def deduplicate_customers(df):
    window = Window.partitionBy("customer_id").orderBy(col("_created_at").asc())
    df = df.withColumn("_row_num", row_number().over(window))
    df = df.filter(col("_row_num") == 1).drop("_row_num")
    return df

# ---- Data Wrangler Generated Code ----
# Operation: Cap outliers in 'lifetime_value' at 99th percentile
def cap_outliers_lifetime_value(df):
    p99 = df.approxQuantile("lifetime_value", [0.99], 0.01)[0]
    df = df.withColumn(
        "lifetime_value",
        when(col("lifetime_value") > lit(p99), lit(p99)).otherwise(col("lifetime_value"))
    )
    return df

print("✅ Data Wrangler transformation functions defined.")
print("   Apply with: df = clean_loyalty_tier(df)")
print("   Apply with: df = standardise_email(df)")
print("   Apply with: df = deduplicate_customers(df)")
print("   Apply with: df = cap_outliers_lifetime_value(df)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Summary
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Source table | `dim_customer` |
# MAGIC | Output table | `dq_customer_profile_report` |
# MAGIC | Columns profiled | All columns in dim_customer |
# MAGIC | Checks performed | Null %, uniqueness, outliers, duplicates, DQ rules |
# MAGIC | Transformations | Fill nulls, standardise email, dedup, cap outliers |
# MAGIC | Schedule | Run before any ML training or analytics refresh |

print("Customer data profiling notebook complete.")
