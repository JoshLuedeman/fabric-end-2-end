# Fabric notebook source
# MAGIC %md
# MAGIC # Data Science — ML-Based Anomaly Detection
# MAGIC
# MAGIC **Purpose:** Detect anomalous sales patterns and inventory movements using
# MAGIC Isolation Forest, complementing the rule-based KQL anomaly detection already
# MAGIC deployed in the real-time analytics workspace.
# MAGIC
# MAGIC **Business Context:** Rule-based anomaly detection (KQL) catches known patterns
# MAGIC like sudden revenue drops or refund spikes. ML-based detection catches unknown or
# MAGIC subtle anomalies — unusual combinations of metrics that individually look normal
# MAGIC but together form a pattern (e.g., a store with normal revenue but unusually low
# MAGIC customer count and high basket size may indicate data issues or fraud).
# MAGIC
# MAGIC **Two Detection Domains:**
# MAGIC 1. **Sales anomalies:** unusual daily sales patterns per store
# MAGIC 2. **Inventory anomalies:** unusual stock movements (potential theft/shrinkage)
# MAGIC
# MAGIC **Data Sources (Gold Layer):**
# MAGIC - `fact_sales` — daily transaction patterns
# MAGIC - `fact_inventory` — stock movement patterns
# MAGIC - `dim_store` — store attributes for context
# MAGIC
# MAGIC **Output:** `ml_anomalies` gold table + MLflow experiment
# MAGIC `tt-anomaly-detection`

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install scikit-learn==1.5.2 matplotlib seaborn --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

from pyspark.sql.functions import (
    col, sum as _sum, count as _count, countDistinct, avg as _avg,
    max as _max, min as _min, datediff, current_date, current_timestamp,
    lit, when, to_date, date_sub, abs as _abs,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import mlflow
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import seaborn as sns

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONTAMINATION_RATE = 0.05  # expected anomaly fraction
RECENT_DAYS = 7            # flag anomalies in last N days
N_ESTIMATORS = 200
RANDOM_STATE = 42
EXPERIMENT_NAME = "tt-anomaly-detection"

print("Imports and configuration loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Read Gold Layer Tables

# COMMAND ----------

print("Reading gold layer tables...")

try:
    df_sales = spark.read.format("delta").table("fact_sales")
    print(f"  fact_sales rows: {df_sales.count():,}")
except Exception as e:
    raise RuntimeError(f"fact_sales table not found. Run gold notebooks first. Error: {e}")

try:
    df_inventory = spark.read.format("delta").table("fact_inventory")
    print(f"  fact_inventory rows: {df_inventory.count():,}")
except Exception as e:
    print(f"  ⚠ fact_inventory not available — skipping inventory anomaly detection. Error: {e}")
    df_inventory = None

try:
    df_store = (
        spark.read.format("delta").table("dim_store")
        .filter(col("is_current") == True)
        .select("store_sk", "store_id", "store_name", "region")
    )
    print(f"  dim_store rows: {df_store.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_store table not found. Error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build Daily Sales Features per Store

# COMMAND ----------

print("Building daily sales features per store...")

# Parse date_key
df_sales_dated = df_sales.withColumn(
    "sale_date",
    to_date(col("date_key").cast("string"), "yyyyMMdd"),
)

# Daily aggregation per store
df_daily_sales = (
    df_sales_dated
    .groupBy("store_sk", "sale_date")
    .agg(
        _sum("total_amount").alias("total_revenue"),
        _count("transaction_id").alias("transaction_count"),
        _avg("total_amount").alias("avg_basket_size"),
        countDistinct("customer_sk").alias("unique_customers"),
        _avg("discount_pct").alias("avg_discount_rate"),
    )
)

# Calculate refund rate proxy: % of transactions with negative net or very high discount
df_refund_rate = (
    df_sales_dated
    .groupBy("store_sk", "sale_date")
    .agg(
        _count(when(col("discount_pct") > 25, True)).alias("high_discount_txns"),
        _count("*").alias("total_txns"),
    )
    .withColumn(
        "refund_rate",
        col("high_discount_txns").cast("double") / col("total_txns"),
    )
    .select("store_sk", "sale_date", "refund_rate")
)

# Join features
df_sales_features = (
    df_daily_sales
    .join(df_refund_rate, on=["store_sk", "sale_date"], how="left")
    .join(df_store, on="store_sk", how="inner")
)

sales_feature_count = df_sales_features.count()
print(f"  Daily sales feature rows: {sales_feature_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Train Isolation Forest on Sales Patterns

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

SALES_FEATURES = [
    "total_revenue",
    "transaction_count",
    "avg_basket_size",
    "unique_customers",
    "avg_discount_rate",
    "refund_rate",
]

print("Training Isolation Forest on sales patterns...")
print("=" * 60)

# Convert to Pandas
pdf_sales = df_sales_features.select(
    ["store_sk", "store_id", "store_name", "sale_date", "region"] + SALES_FEATURES
).toPandas()

# Fill nulls
pdf_sales[SALES_FEATURES] = pdf_sales[SALES_FEATURES].fillna(0)

# Standardise
sales_scaler = StandardScaler()
X_sales = sales_scaler.fit_transform(pdf_sales[SALES_FEATURES])

with mlflow.start_run(run_name="sales-anomaly-isolation-forest"):
    mlflow.log_params({
        "domain": "sales",
        "algorithm": "IsolationForest",
        "n_estimators": N_ESTIMATORS,
        "contamination": CONTAMINATION_RATE,
        "features": ", ".join(SALES_FEATURES),
        "n_samples": len(pdf_sales),
    })

    # Train model
    iso_sales = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION_RATE,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    pdf_sales["anomaly_score"] = iso_sales.fit_predict(X_sales)
    pdf_sales["anomaly_raw_score"] = iso_sales.decision_function(X_sales)

    # -1 = anomaly, 1 = normal
    pdf_sales["is_anomaly"] = (pdf_sales["anomaly_score"] == -1).astype(int)

    total_anomalies = pdf_sales["is_anomaly"].sum()
    anomaly_pct = total_anomalies / len(pdf_sales) * 100

    mlflow.log_metrics({
        "total_anomalies": total_anomalies,
        "anomaly_pct": round(anomaly_pct, 2),
        "mean_anomaly_score": round(pdf_sales["anomaly_raw_score"].mean(), 4),
        "threshold": round(iso_sales.offset_, 4),
    })

    print(f"  Total daily records:   {len(pdf_sales):,}")
    print(f"  Anomalies detected:    {total_anomalies:,} ({anomaly_pct:.1f}%)")

# Flag recent anomalies (last 7 days)
recent_cutoff = pd.Timestamp.now() - pd.Timedelta(days=RECENT_DAYS)
pdf_sales["sale_date"] = pd.to_datetime(pdf_sales["sale_date"])
pdf_recent_sales = pdf_sales[
    (pdf_sales["is_anomaly"] == 1) & (pdf_sales["sale_date"] >= recent_cutoff)
]
print(f"  Recent anomalies (last {RECENT_DAYS} days): {len(pdf_recent_sales):,}")
pdf_sales["anomaly_domain"] = "sales"

print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Build Inventory Features & Detect Anomalies

# COMMAND ----------

all_anomalies = [pdf_sales[pdf_sales["is_anomaly"] == 1].copy()]

if df_inventory is not None:
    print("Building inventory anomaly features...")
    print("=" * 60)

    # Parse date_key
    df_inv_dated = df_inventory.withColumn(
        "movement_date",
        to_date(col("date_key").cast("string"), "yyyyMMdd"),
    )

    # Daily inventory features per store
    df_daily_inv = (
        df_inv_dated
        .groupBy("store_sk", "movement_date")
        .agg(
            _sum("quantity").alias("net_quantity_change"),
            _count("inventory_id").alias("movement_count"),
            _sum(when(col("movement_type") == "Return", col("quantity")).otherwise(0))
                .alias("return_quantity"),
            _sum(when(col("movement_type") == "Adjustment", _abs(col("quantity"))).otherwise(0))
                .alias("adjustment_quantity"),
            _avg("on_hand_after").alias("avg_on_hand"),
            _sum(when(col("is_below_reorder") == True, 1).otherwise(0))
                .alias("below_reorder_count"),
        )
        .join(df_store, on="store_sk", how="inner")
    )

    INV_FEATURES = [
        "net_quantity_change",
        "movement_count",
        "return_quantity",
        "adjustment_quantity",
        "avg_on_hand",
        "below_reorder_count",
    ]

    pdf_inv = df_daily_inv.select(
        ["store_sk", "store_id", "store_name", "movement_date", "region"] + INV_FEATURES
    ).toPandas()

    pdf_inv[INV_FEATURES] = pdf_inv[INV_FEATURES].fillna(0)

    # Standardise
    inv_scaler = StandardScaler()
    X_inv = inv_scaler.fit_transform(pdf_inv[INV_FEATURES])

    with mlflow.start_run(run_name="inventory-anomaly-isolation-forest"):
        mlflow.log_params({
            "domain": "inventory",
            "algorithm": "IsolationForest",
            "n_estimators": N_ESTIMATORS,
            "contamination": CONTAMINATION_RATE,
            "features": ", ".join(INV_FEATURES),
            "n_samples": len(pdf_inv),
        })

        iso_inv = IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION_RATE,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        pdf_inv["anomaly_score"] = iso_inv.fit_predict(X_inv)
        pdf_inv["anomaly_raw_score"] = iso_inv.decision_function(X_inv)
        pdf_inv["is_anomaly"] = (pdf_inv["anomaly_score"] == -1).astype(int)

        inv_anomalies = pdf_inv["is_anomaly"].sum()
        inv_anomaly_pct = inv_anomalies / len(pdf_inv) * 100

        mlflow.log_metrics({
            "total_anomalies": inv_anomalies,
            "anomaly_pct": round(inv_anomaly_pct, 2),
            "mean_anomaly_score": round(pdf_inv["anomaly_raw_score"].mean(), 4),
            "threshold": round(iso_inv.offset_, 4),
        })

        print(f"  Total inventory records: {len(pdf_inv):,}")
        print(f"  Anomalies detected:      {inv_anomalies:,} ({inv_anomaly_pct:.1f}%)")

    # Recent inventory anomalies
    pdf_inv["movement_date"] = pd.to_datetime(pdf_inv["movement_date"])
    pdf_recent_inv = pdf_inv[
        (pdf_inv["is_anomaly"] == 1) & (pdf_inv["movement_date"] >= recent_cutoff)
    ]
    print(f"  Recent inventory anomalies (last {RECENT_DAYS} days): {len(pdf_recent_inv):,}")

    # Rename date column for consistent output
    pdf_inv_anomalies = pdf_inv[pdf_inv["is_anomaly"] == 1].copy()
    pdf_inv_anomalies["anomaly_domain"] = "inventory"
    pdf_inv_anomalies.rename(columns={"movement_date": "sale_date"}, inplace=True)
    all_anomalies.append(pdf_inv_anomalies)

    print("=" * 60)
else:
    print("⚠ Inventory data not available — skipping inventory anomaly detection.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Combine and Write Anomalies to Gold Table

# COMMAND ----------

print("Combining anomalies and writing to ml_anomalies...")

# Standardise columns across domains
output_cols = [
    "store_id", "store_name", "region", "sale_date",
    "anomaly_domain", "anomaly_raw_score", "is_anomaly",
]

combined_parts = []
for part in all_anomalies:
    available_cols = [c for c in output_cols if c in part.columns]
    combined_parts.append(part[available_cols])

pdf_combined = pd.concat(combined_parts, ignore_index=True)

df_anomalies = spark.createDataFrame(pdf_combined)
df_anomalies = (
    df_anomalies
    .withColumnRenamed("sale_date", "anomaly_date")
    .withColumn("_created_at", current_timestamp())
)

(
    df_anomalies
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("ml_anomalies")
)

row_count = df_anomalies.count()
print(f"✅ ml_anomalies written: {row_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Compare with KQL-Detected Anomalies (Validation)
# MAGIC
# MAGIC If KQL-based anomaly results are available, compare overlap to validate
# MAGIC both detection approaches.

# COMMAND ----------

print("Checking for KQL-detected anomalies for cross-validation...")

try:
    df_kql_anomalies = spark.read.format("delta").table("kql_anomalies")
    kql_count = df_kql_anomalies.count()
    print(f"  KQL anomalies found: {kql_count:,}")

    # Join ML anomalies with KQL anomalies on store + date
    df_ml_recent = df_anomalies.filter(col("anomaly_domain") == "sales")
    df_overlap = (
        df_ml_recent
        .join(
            df_kql_anomalies.select("store_id", "anomaly_date"),
            on=["store_id", "anomaly_date"],
            how="inner",
        )
    )
    overlap_count = df_overlap.count()
    print(f"  Overlap (ML ∩ KQL):   {overlap_count:,}")
    if row_count > 0:
        print(f"  Overlap rate:         {overlap_count / row_count * 100:.1f}%")
except Exception:
    print("  ⚠ KQL anomaly table not available — skipping cross-validation.")
    print("  This is expected if real-time analytics has not run anomaly detection yet.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Visualisation — Anomaly Distribution

# COMMAND ----------

print("Generating anomaly visualisation...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Plot 1: Sales anomaly score distribution
ax1 = axes[0, 0]
ax1.hist(
    pdf_sales["anomaly_raw_score"], bins=50, color="steelblue", alpha=0.7,
    edgecolor="black", linewidth=0.3,
)
ax1.axvline(
    x=iso_sales.offset_, color="red", linestyle="--",
    label=f"Threshold ({iso_sales.offset_:.3f})",
)
ax1.set_title("Sales Anomaly Score Distribution", fontsize=11)
ax1.set_xlabel("Anomaly Score")
ax1.set_ylabel("Frequency")
ax1.legend()

# Plot 2: Anomalies by store (top 10)
ax2 = axes[0, 1]
store_anomaly_counts = (
    pdf_sales[pdf_sales["is_anomaly"] == 1]
    .groupby("store_name")
    .size()
    .sort_values(ascending=True)
    .tail(10)
)
if len(store_anomaly_counts) > 0:
    store_anomaly_counts.plot(kind="barh", ax=ax2, color="coral")
ax2.set_title("Top 10 Stores by Sales Anomaly Count", fontsize=11)
ax2.set_xlabel("Anomaly Count")

# Plot 3: Anomalies over time
ax3 = axes[1, 0]
daily_anomaly_ts = (
    pdf_sales[pdf_sales["is_anomaly"] == 1]
    .groupby("sale_date")
    .size()
)
if len(daily_anomaly_ts) > 0:
    ax3.plot(daily_anomaly_ts.index, daily_anomaly_ts.values, color="red", alpha=0.7)
ax3.set_title("Sales Anomalies Over Time", fontsize=11)
ax3.set_xlabel("Date")
ax3.set_ylabel("Daily Anomaly Count")
ax3.tick_params(axis="x", rotation=30)

# Plot 4: Domain breakdown
ax4 = axes[1, 1]
domain_counts = pdf_combined["anomaly_domain"].value_counts()
ax4.pie(
    domain_counts.values, labels=domain_counts.index,
    autopct="%1.1f%%", colors=["steelblue", "coral"],
    startangle=90,
)
ax4.set_title("Anomalies by Domain", fontsize=11)

plt.suptitle("Tales & Timber ML Anomaly Detection Dashboard", fontsize=14)
plt.tight_layout()
plt.savefig("/tmp/anomaly_detection_viz.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Visualisation rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |---|---|
# MAGIC | Algorithm | Isolation Forest |
# MAGIC | Contamination rate | 5% (configurable) |
# MAGIC | Sales features | revenue, txn count, basket size, unique customers, discount rate, refund rate |
# MAGIC | Inventory features | net quantity, movement count, returns, adjustments, on-hand, below-reorder |
# MAGIC | Recent window | Last 7 days |
# MAGIC | Output table | `ml_anomalies` |
# MAGIC | MLflow experiment | `tt-anomaly-detection` |
# MAGIC | Cross-validation | Compared with KQL-detected anomalies when available |

print("Anomaly detection notebook complete.")
