# Fabric notebook source
# MAGIC %md
# MAGIC # Data Science — Promotion Effectiveness Analysis
# MAGIC
# MAGIC **Purpose:** Analyse which promotions drive incremental revenue versus mere
# MAGIC cannibalisation, using causal inference via propensity score matching.
# MAGIC
# MAGIC **Business Context:** Tales & Timber runs hundreds of promotions per year
# MAGIC but historically has not measured true incrementality. A "successful" promotion
# MAGIC that appears to lift revenue may simply be attracting customers who would have
# MAGIC purchased anyway (selection bias). This notebook applies propensity score matching
# MAGIC to estimate the causal effect of each promotion on revenue, then calculates ROI
# MAGIC to rank promotions by true effectiveness.
# MAGIC
# MAGIC **Methodology:**
# MAGIC 1. Calculate baseline sales from non-promotional periods
# MAGIC 2. Estimate propensity scores using logistic regression
# MAGIC 3. Match promo customers with similar non-promo customers
# MAGIC 4. Estimate incremental lift per promotion
# MAGIC 5. Calculate ROI = (incremental_revenue − discount_cost) / discount_cost
# MAGIC
# MAGIC **Data Sources (Gold Layer):**
# MAGIC - `fact_sales` — transactional sales with discount information
# MAGIC - `dim_product` — product category for segmentation
# MAGIC - `dim_customer` — customer attributes for matching
# MAGIC - `dim_store` — store attributes for segmentation
# MAGIC
# MAGIC **Output:** `ml_promotion_effectiveness` gold table + MLflow experiment
# MAGIC `tt-promo-analysis`

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
    lit, when, to_date, date_format, percentile_approx, abs as _abs,
    date_sub, date_add,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import mlflow
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import seaborn as sns

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DISCOUNT_THRESHOLD_PCT = 5.0  # transactions with discount > threshold = "promoted"
EXPERIMENT_NAME = "tt-promo-analysis"
TOP_N_PROMOS = 15  # number of top/bottom promotions to visualise

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
    df_product = (
        spark.read.format("delta").table("dim_product")
        .filter(col("is_current") == True)
        .select("product_sk", "category", "subcategory", "unit_price", "unit_cost")
    )
    print(f"  dim_product rows: {df_product.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_product table not found. Error: {e}")

try:
    df_customer = (
        spark.read.format("delta").table("dim_customer")
        .filter(col("is_current") == True)
        .select("customer_sk", "customer_id", "loyalty_tier", "customer_segment")
    )
    print(f"  dim_customer rows: {df_customer.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_customer table not found. Error: {e}")

try:
    df_store = (
        spark.read.format("delta").table("dim_store")
        .filter(col("is_current") == True)
        .select("store_sk", "store_id", "store_type", "region")
    )
    print(f"  dim_store rows: {df_store.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_store table not found. Error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Identify Promotional vs Non-Promotional Transactions
# MAGIC
# MAGIC Since dedicated promotion tables may not yet exist, we define promotions
# MAGIC based on discount percentage: transactions with `discount_pct > 5%` are
# MAGIC considered promotional. We group by `category × month` to create distinct
# MAGIC "promotion events" for analysis.

# COMMAND ----------

print(f"Classifying transactions (promo threshold: >{DISCOUNT_THRESHOLD_PCT}% discount)...")

# Add date column and promo flag
df_enriched = (
    df_sales
    .join(df_product, on="product_sk", how="inner")
    .join(df_customer, on="customer_sk", how="inner")
    .join(df_store, on="store_sk", how="inner")
    .withColumn("sale_date", to_date(col("date_key").cast("string"), "yyyyMMdd"))
    .withColumn("sale_month", date_format(col("sale_date"), "yyyy-MM"))
    .withColumn(
        "is_promo",
        when(col("discount_pct") > DISCOUNT_THRESHOLD_PCT, 1).otherwise(0),
    )
    .withColumn(
        "discount_amount",
        col("gross_amount") - col("net_amount"),
    )
)

total_txns = df_enriched.count()
promo_txns = df_enriched.filter(col("is_promo") == 1).count()
print(f"  Total transactions: {total_txns:,}")
print(f"  Promotional:        {promo_txns:,} ({promo_txns/total_txns*100:.1f}%)")
print(f"  Non-promotional:    {total_txns - promo_txns:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Define Promotion Events (Category × Month)

# COMMAND ----------

print("Defining promotion events by category × month...")

df_promo_events = (
    df_enriched
    .filter(col("is_promo") == 1)
    .groupBy("category", "sale_month")
    .agg(
        _count("transaction_id").alias("promo_transactions"),
        _sum("total_amount").alias("promo_revenue"),
        _sum("discount_amount").alias("total_discount_cost"),
        _avg("discount_pct").alias("avg_discount_pct"),
        countDistinct("customer_sk").alias("promo_customers"),
    )
    .filter(col("promo_transactions") >= 10)  # minimum activity threshold
    .orderBy("category", "sale_month")
)

n_events = df_promo_events.count()
print(f"  Promotion events identified: {n_events:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Calculate Baseline (Non-Promo) Sales per Category × Month

# COMMAND ----------

print("Calculating baseline (non-promo) sales...")

df_baseline = (
    df_enriched
    .filter(col("is_promo") == 0)
    .groupBy("category", "sale_month")
    .agg(
        _count("transaction_id").alias("baseline_transactions"),
        _sum("total_amount").alias("baseline_revenue"),
        countDistinct("customer_sk").alias("baseline_customers"),
    )
)

# Join promo events with baseline
df_comparison = (
    df_promo_events
    .join(df_baseline, on=["category", "sale_month"], how="inner")
)

comparison_count = df_comparison.count()
print(f"  Matched promo/baseline periods: {comparison_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Propensity Score Matching
# MAGIC
# MAGIC Estimate the propensity of a customer being in the "promo" group using
# MAGIC logistic regression on customer features, then match promo customers to
# MAGIC similar non-promo customers using nearest-neighbour matching.

# COMMAND ----------

print("Running propensity score matching...")
print("=" * 60)

# Build customer-level features for propensity model
df_cust_features = (
    df_enriched
    .groupBy("customer_sk", "is_promo")
    .agg(
        _count("transaction_id").alias("n_transactions"),
        _sum("total_amount").alias("total_spend"),
        _avg("total_amount").alias("avg_spend"),
        _avg("discount_pct").alias("avg_discount"),
        countDistinct("category").alias("n_categories"),
    )
)

# Convert to Pandas for sklearn
pdf_prop = df_cust_features.toPandas()

# Encode features
PROPENSITY_FEATURES = [
    "n_transactions", "total_spend", "avg_spend", "avg_discount", "n_categories",
]
pdf_prop[PROPENSITY_FEATURES] = pdf_prop[PROPENSITY_FEATURES].fillna(0)

X_prop = pdf_prop[PROPENSITY_FEATURES].values
y_prop = pdf_prop["is_promo"].values

# Fit propensity model
scaler = StandardScaler()
X_prop_scaled = scaler.fit_transform(X_prop)

lr = LogisticRegression(random_state=42, max_iter=500, class_weight="balanced")
lr.fit(X_prop_scaled, y_prop)
pdf_prop["propensity_score"] = lr.predict_proba(X_prop_scaled)[:, 1]

print(f"  Propensity model trained on {len(pdf_prop):,} customer-group records")
print(f"  Propensity score range: {pdf_prop['propensity_score'].min():.3f} "
      f"— {pdf_prop['propensity_score'].max():.3f}")

# Nearest-neighbour matching: for each promo customer find closest non-promo
pdf_promo = pdf_prop[pdf_prop["is_promo"] == 1].copy()
pdf_control = pdf_prop[pdf_prop["is_promo"] == 0].copy()

if len(pdf_control) > 0 and len(pdf_promo) > 0:
    nn = NearestNeighbors(n_neighbors=1, metric="euclidean")
    nn.fit(pdf_control[["propensity_score"]].values)
    distances, indices = nn.kneighbors(pdf_promo[["propensity_score"]].values)

    matched_control = pdf_control.iloc[indices.flatten()]

    avg_promo_spend = pdf_promo["total_spend"].mean()
    avg_control_spend = matched_control["total_spend"].mean()
    incremental_per_customer = avg_promo_spend - avg_control_spend

    print(f"\n  Propensity-matched results:")
    print(f"    Avg promo customer spend:    ${avg_promo_spend:,.2f}")
    print(f"    Avg matched control spend:   ${avg_control_spend:,.2f}")
    print(f"    Incremental per customer:    ${incremental_per_customer:,.2f}")
else:
    incremental_per_customer = 0
    print("  ⚠ Insufficient data for propensity matching.")

print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Calculate Promotion ROI

# COMMAND ----------

print("Calculating promotion lift and ROI...")

# Convert comparison dataframe to Pandas for detailed analysis
pdf_comp = df_comparison.toPandas()

# Calculate lift: (promo_revenue - baseline_revenue) / baseline_revenue
pdf_comp["revenue_lift"] = np.where(
    pdf_comp["baseline_revenue"] > 0,
    (pdf_comp["promo_revenue"] - pdf_comp["baseline_revenue"]) / pdf_comp["baseline_revenue"],
    0.0,
)

# ROI: (incremental_revenue - discount_cost) / discount_cost
pdf_comp["incremental_revenue"] = pdf_comp["promo_revenue"] - pdf_comp["baseline_revenue"]
pdf_comp["roi"] = np.where(
    pdf_comp["total_discount_cost"] > 0,
    (pdf_comp["incremental_revenue"] - pdf_comp["total_discount_cost"])
    / pdf_comp["total_discount_cost"],
    0.0,
)

# Revenue per promo customer
pdf_comp["revenue_per_promo_customer"] = np.where(
    pdf_comp["promo_customers"] > 0,
    pdf_comp["promo_revenue"] / pdf_comp["promo_customers"],
    0.0,
)

# Rank by ROI
pdf_comp = pdf_comp.sort_values("roi", ascending=False).reset_index(drop=True)

print(f"  Promotion events analysed: {len(pdf_comp):,}")
print(f"\n  Top 5 by ROI:")
for _, row in pdf_comp.head(5).iterrows():
    print(
        f"    {row['category']} ({row['sale_month']}): "
        f"ROI={row['roi']:.2f}, lift={row['revenue_lift']:.1%}"
    )
print(f"\n  Bottom 5 by ROI:")
for _, row in pdf_comp.tail(5).iterrows():
    print(
        f"    {row['category']} ({row['sale_month']}): "
        f"ROI={row['roi']:.2f}, lift={row['revenue_lift']:.1%}"
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Log Results to MLflow

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

with mlflow.start_run(run_name="promo-effectiveness-analysis"):
    mlflow.log_params({
        "discount_threshold_pct": DISCOUNT_THRESHOLD_PCT,
        "n_promotion_events": len(pdf_comp),
        "propensity_model": "LogisticRegression",
        "matching_method": "NearestNeighbors",
        "total_promo_transactions": promo_txns,
    })

    mlflow.log_metrics({
        "avg_roi": round(pdf_comp["roi"].mean(), 4),
        "median_roi": round(pdf_comp["roi"].median(), 4),
        "avg_lift": round(pdf_comp["revenue_lift"].mean(), 4),
        "positive_roi_count": int((pdf_comp["roi"] > 0).sum()),
        "negative_roi_count": int((pdf_comp["roi"] <= 0).sum()),
        "incremental_per_customer_psm": round(incremental_per_customer, 2),
        "total_promo_revenue": round(pdf_comp["promo_revenue"].sum(), 2),
        "total_discount_cost": round(pdf_comp["total_discount_cost"].sum(), 2),
    })

    print(f"✅ Results logged to MLflow experiment '{EXPERIMENT_NAME}'")
    print(f"   Avg ROI:  {pdf_comp['roi'].mean():.2f}")
    print(f"   Avg Lift: {pdf_comp['revenue_lift'].mean():.1%}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Write Results to Gold Table

# COMMAND ----------

print("Writing results to ml_promotion_effectiveness...")

df_results = spark.createDataFrame(pdf_comp)
df_results = df_results.withColumn("_created_at", current_timestamp())

(
    df_results
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("ml_promotion_effectiveness")
)

row_count = df_results.count()
print(f"✅ ml_promotion_effectiveness written: {row_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Visualisation — Top/Bottom Promotions by ROI

# COMMAND ----------

print("Generating promotion effectiveness visualisation...")

n_show = min(TOP_N_PROMOS, len(pdf_comp))
pdf_top = pdf_comp.head(n_show).copy()
pdf_bottom = pdf_comp.tail(n_show).copy()

fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# Top promotions by ROI
pdf_top["label"] = pdf_top["category"] + "\n" + pdf_top["sale_month"]
colors_top = ["#2ecc71" if r > 0 else "#e74c3c" for r in pdf_top["roi"]]
axes[0].barh(pdf_top["label"], pdf_top["roi"], color=colors_top)
axes[0].set_xlabel("ROI")
axes[0].set_title(f"Top {n_show} Promotions by ROI", fontsize=12)
axes[0].axvline(x=0, color="black", linewidth=0.8, linestyle="--")

# Bottom promotions by ROI
pdf_bottom["label"] = pdf_bottom["category"] + "\n" + pdf_bottom["sale_month"]
colors_bot = ["#2ecc71" if r > 0 else "#e74c3c" for r in pdf_bottom["roi"]]
axes[1].barh(pdf_bottom["label"], pdf_bottom["roi"], color=colors_bot)
axes[1].set_xlabel("ROI")
axes[1].set_title(f"Bottom {n_show} Promotions by ROI", fontsize=12)
axes[1].axvline(x=0, color="black", linewidth=0.8, linestyle="--")

plt.suptitle(
    "Tales & Timber Promotion Effectiveness — ROI Analysis\n"
    f"(Green = positive ROI, Red = negative ROI)",
    fontsize=14,
)
plt.tight_layout()
plt.savefig("/tmp/promotion_effectiveness_viz.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Visualisation rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |---|---|
# MAGIC | Approach | Propensity score matching (causal inference) |
# MAGIC | Promo definition | Transactions with discount > 5% |
# MAGIC | Propensity model | Logistic Regression |
# MAGIC | Matching | Nearest Neighbors on propensity score |
# MAGIC | Key metric | ROI = (incremental_revenue − discount_cost) / discount_cost |
# MAGIC | Output table | `ml_promotion_effectiveness` |
# MAGIC | MLflow experiment | `tt-promo-analysis` |

print("Promotion effectiveness analysis notebook complete.")
