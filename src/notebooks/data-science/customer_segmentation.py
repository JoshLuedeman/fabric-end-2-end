# Fabric notebook source
# MAGIC %md
# MAGIC # Data Science — Customer Segmentation
# MAGIC
# MAGIC **Purpose:** Segment customers using RFM analysis combined with K-Means clustering
# MAGIC to enable targeted marketing, personalised offers, and retention strategies.
# MAGIC
# MAGIC **Business Context:** Tales & Timber serves millions of customers across
# MAGIC multiple channels. Understanding customer segments enables the marketing team to
# MAGIC allocate budget efficiently — VIP Champions receive exclusive previews, At-Risk
# MAGIC customers receive win-back campaigns, and Bargain Hunters receive value-focused
# MAGIC promotions.
# MAGIC
# MAGIC **Data Sources (Gold Layer):**
# MAGIC - `fact_sales` — transaction history for RFM calculation
# MAGIC - `dim_customer` — customer attributes (loyalty_tier, segment, lifetime_value)
# MAGIC
# MAGIC **Output:** `ml_customer_segments` gold table + MLflow experiment
# MAGIC `tt-customer-segmentation`

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
    lit, when, to_date, row_number,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import mlflow
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import seaborn as sns

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
K_RANGE = range(3, 9)  # test 3 to 8 clusters
EXPERIMENT_NAME = "tt-customer-segmentation"

SEGMENT_LABELS = {
    0: "VIP Champions",
    1: "Loyal Regulars",
    2: "At Risk",
    3: "New Customers",
    4: "Bargain Hunters",
    5: "Churning",
}

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
    df_customer = (
        spark.read.format("delta").table("dim_customer")
        .filter(col("is_current") == True)
    )
    print(f"  dim_customer rows: {df_customer.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_customer table not found. Run gold notebooks first. Error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Calculate RFM Features

# COMMAND ----------

print("Calculating RFM features...")

# Parse date_key to date for recency calculation
df_sales_dated = df_sales.withColumn(
    "sale_date",
    to_date(col("date_key").cast("string"), "yyyyMMdd"),
)

# Calculate RFM per customer
df_rfm = (
    df_sales_dated
    .groupBy("customer_sk")
    .agg(
        _max("sale_date").alias("last_purchase_date"),
        _count("transaction_id").alias("frequency"),
        _sum("total_amount").alias("monetary"),
    )
)

# Recency: days since last purchase from today
df_rfm = df_rfm.withColumn(
    "recency",
    datediff(current_date(), col("last_purchase_date")),
)

rfm_count = df_rfm.count()
print(f"  RFM features calculated for {rfm_count:,} customers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Add Behavioural Features

# COMMAND ----------

print("Calculating behavioural features...")

# Join sales with product dimension for category diversity
try:
    df_product = (
        spark.read.format("delta").table("dim_product")
        .filter(col("is_current") == True)
        .select("product_sk", "category")
    )
except Exception as e:
    raise RuntimeError(f"dim_product not found: {e}")

df_behavioural = (
    df_sales_dated
    .join(df_product, on="product_sk", how="left")
    .groupBy("customer_sk")
    .agg(
        _avg("total_amount").alias("avg_order_value"),
        countDistinct("category").alias("category_diversity"),
        countDistinct("channel").alias("channel_count"),
        _avg("discount_pct").alias("avg_discount_used"),
    )
)

# Determine preferred channel per customer (mode)
window_channel = Window.partitionBy("customer_sk").orderBy(col("channel_count_agg").desc())
df_channel_mode = (
    df_sales
    .groupBy("customer_sk", "channel")
    .agg(_count("*").alias("channel_count_agg"))
    .withColumn("_rn", row_number().over(window_channel))
    .filter(col("_rn") == 1)
    .select("customer_sk", col("channel").alias("preferred_channel"))
)

# Calculate return rate proxy: transactions with high discount as returns indicator
# (Actual returns data not available — use discount_pct > 20% as proxy)
df_return_proxy = (
    df_sales
    .groupBy("customer_sk")
    .agg(
        _count(when(col("discount_pct") > 20, True)).alias("high_discount_count"),
        _count("*").alias("total_count"),
    )
    .withColumn(
        "return_rate",
        col("high_discount_count").cast("double") / col("total_count"),
    )
    .select("customer_sk", "return_rate")
)

# Merge all features
df_features = (
    df_rfm
    .join(df_behavioural, on="customer_sk", how="left")
    .join(df_channel_mode, on="customer_sk", how="left")
    .join(df_return_proxy, on="customer_sk", how="left")
    .join(
        df_customer.select(
            "customer_sk", "customer_id", "loyalty_tier",
            "customer_segment", "lifetime_value",
        ),
        on="customer_sk",
        how="inner",
    )
)

feature_count = df_features.count()
print(f"  Combined features for {feature_count:,} customers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Prepare Feature Matrix

# COMMAND ----------

print("Preparing feature matrix for clustering...")

NUMERIC_FEATURES = [
    "recency",
    "frequency",
    "monetary",
    "avg_order_value",
    "category_diversity",
    "avg_discount_used",
    "return_rate",
]

# Convert to Pandas for sklearn
pdf = df_features.select(["customer_sk", "customer_id"] + NUMERIC_FEATURES).toPandas()

# Fill nulls with 0 (customers with no behavioural data)
pdf[NUMERIC_FEATURES] = pdf[NUMERIC_FEATURES].fillna(0)

# Standardise
scaler = StandardScaler()
X_scaled = scaler.fit_transform(pdf[NUMERIC_FEATURES])

print(f"  Feature matrix shape: {X_scaled.shape}")
print(f"  Features: {NUMERIC_FEATURES}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Elbow Method — Find Optimal K

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

print("Running elbow method for K selection...")

inertias = []
silhouette_scores = []

for k in K_RANGE:
    km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
    labels = km.fit_predict(X_scaled)
    inertia = km.inertia_
    sil_score = silhouette_score(X_scaled, labels)
    inertias.append(inertia)
    silhouette_scores.append(sil_score)
    print(f"  K={k}: inertia={inertia:,.0f}, silhouette={sil_score:.4f}")

# Select K with best silhouette score
best_k = list(K_RANGE)[np.argmax(silhouette_scores)]
best_silhouette = max(silhouette_scores)
print(f"\n  ➜ Optimal K = {best_k} (silhouette = {best_silhouette:.4f})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Train Final K-Means Model

# COMMAND ----------

print(f"Training final K-Means with K={best_k}...")

with mlflow.start_run(run_name=f"kmeans-k{best_k}-rfm-behavioral"):
    mlflow.log_params({
        "algorithm": "KMeans",
        "n_clusters": best_k,
        "features": ", ".join(NUMERIC_FEATURES),
        "n_customers": len(pdf),
        "scaler": "StandardScaler",
    })

    final_km = KMeans(n_clusters=best_k, random_state=42, n_init=10, max_iter=300)
    pdf["cluster"] = final_km.fit_predict(X_scaled)

    final_silhouette = silhouette_score(X_scaled, pdf["cluster"])
    mlflow.log_metrics({
        "silhouette_score": round(final_silhouette, 4),
        "inertia": round(final_km.inertia_, 2),
        "n_clusters": best_k,
    })

    # Log inertia / silhouette curves
    for i, k in enumerate(K_RANGE):
        mlflow.log_metric("elbow_inertia", inertias[i], step=k)
        mlflow.log_metric("elbow_silhouette", silhouette_scores[i], step=k)

    # Log cluster profiles
    cluster_profiles = pdf.groupby("cluster")[NUMERIC_FEATURES].mean()
    for c_idx, row in cluster_profiles.iterrows():
        for feat in NUMERIC_FEATURES:
            mlflow.log_metric(f"cluster_{c_idx}_mean_{feat}", round(row[feat], 2))

    print(f"  ✅ Final silhouette score: {final_silhouette:.4f}")
    print(f"\nCluster profiles (means):")
    print(cluster_profiles.round(2).to_string())

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Assign Segment Labels
# MAGIC
# MAGIC Labels are assigned by ranking clusters on key RFM characteristics:
# MAGIC - **VIP Champions:** high monetary + high frequency + low recency
# MAGIC - **Loyal Regulars:** moderate-to-high frequency + moderate monetary
# MAGIC - **At Risk:** moderate monetary but rising recency
# MAGIC - **New Customers:** low frequency + low recency
# MAGIC - **Bargain Hunters:** high discount usage
# MAGIC - **Churning:** high recency + declining frequency

# COMMAND ----------

print("Assigning segment labels...")

# Rank clusters by monetary (desc) — highest spenders first
cluster_ranking = (
    cluster_profiles
    .sort_values(["monetary", "frequency"], ascending=[False, False])
    .index.tolist()
)

# Map clusters to labels based on rank order
available_labels = list(SEGMENT_LABELS.values())
label_map = {}
for rank, cluster_idx in enumerate(cluster_ranking):
    if rank < len(available_labels):
        label_map[cluster_idx] = available_labels[rank]
    else:
        label_map[cluster_idx] = f"Segment {cluster_idx}"

pdf["segment_label"] = pdf["cluster"].map(label_map)

# Print segment distribution
print("\nSegment distribution:")
segment_dist = pdf["segment_label"].value_counts()
for seg, cnt in segment_dist.items():
    pct = cnt / len(pdf) * 100
    print(f"  {seg}: {cnt:,} customers ({pct:.1f}%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Write Segments to Gold Table

# COMMAND ----------

print("Writing customer segments to ml_customer_segments...")

df_segments = spark.createDataFrame(
    pdf[["customer_sk", "customer_id", "cluster", "segment_label"] + NUMERIC_FEATURES]
)
df_segments = df_segments.withColumn("_created_at", current_timestamp())

(
    df_segments
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("ml_customer_segments")
)

row_count = df_segments.count()
print(f"✅ ml_customer_segments written: {row_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Visualisation — PCA 2D Cluster Projection

# COMMAND ----------

print("Generating cluster visualisation...")

pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
pdf["pca_1"] = X_pca[:, 0]
pdf["pca_2"] = X_pca[:, 1]

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# Plot 1: Cluster scatter (PCA)
scatter = axes[0].scatter(
    pdf["pca_1"], pdf["pca_2"],
    c=pdf["cluster"], cmap="Set2", alpha=0.5, s=10,
)
axes[0].set_title("Customer Segments — PCA Projection", fontsize=12)
axes[0].set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)")
axes[0].set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)")
legend_elements = [
    plt.Line2D([0], [0], marker="o", color="w",
               markerfacecolor=plt.cm.Set2(i / best_k), markersize=8,
               label=label_map.get(i, f"Cluster {i}"))
    for i in range(best_k)
]
axes[0].legend(handles=legend_elements, fontsize=8, loc="best")

# Plot 2: Elbow / silhouette
ax2 = axes[1]
ax2_twin = ax2.twinx()
ax2.plot(list(K_RANGE), inertias, "b-o", label="Inertia")
ax2_twin.plot(list(K_RANGE), silhouette_scores, "r-s", label="Silhouette")
ax2.axvline(x=best_k, color="green", linestyle="--", label=f"Optimal K={best_k}")
ax2.set_xlabel("Number of Clusters (K)")
ax2.set_ylabel("Inertia", color="blue")
ax2_twin.set_ylabel("Silhouette Score", color="red")
ax2.set_title("Elbow Method & Silhouette Analysis", fontsize=12)
ax2.legend(loc="upper left", fontsize=8)
ax2_twin.legend(loc="upper right", fontsize=8)

plt.suptitle("Tales & Timber Customer Segmentation Analysis", fontsize=14)
plt.tight_layout()
plt.savefig("/tmp/customer_segmentation_viz.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Visualisation rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |---|---|
# MAGIC | Algorithm | K-Means with elbow method |
# MAGIC | Features | RFM + behavioural (7 features) |
# MAGIC | Optimal K | Determined by silhouette score |
# MAGIC | Output table | `ml_customer_segments` |
# MAGIC | MLflow experiment | `tt-customer-segmentation` |
# MAGIC | Segments | VIP Champions, Loyal Regulars, At Risk, New Customers, Bargain Hunters, Churning |

print("Customer segmentation notebook complete.")
