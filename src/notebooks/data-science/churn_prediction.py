# Fabric notebook source
# MAGIC %md
# MAGIC # Data Science — Churn Prediction
# MAGIC
# MAGIC **Purpose:** Predict which customers are likely to churn in the next 90 days using
# MAGIC gradient boosting classification.
# MAGIC
# MAGIC **Business Context:** Customer acquisition costs at Tales & Timber are 5-7×
# MAGIC higher than retention costs. Identifying at-risk customers early enables the
# MAGIC retention team to deploy targeted win-back campaigns (personalised offers, loyalty
# MAGIC bonuses, outreach calls) before the customer lapses.
# MAGIC
# MAGIC **Churn Definition:** A customer has churned if they have made no purchase in the
# MAGIC last 90 days, provided they have at least 6 months of purchase history.
# MAGIC
# MAGIC **Data Sources (Gold Layer):**
# MAGIC - `fact_sales` — transaction history for feature engineering
# MAGIC - `dim_customer` — customer attributes (loyalty_tier, lifetime_value)
# MAGIC - `dim_product` — product category for diversity features
# MAGIC
# MAGIC **Output:** `ml_churn_predictions` gold table + MLflow experiment
# MAGIC `tt-churn-prediction` + registered model `churn-predictor`

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install lightgbm scikit-learn==1.5.2 matplotlib seaborn --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

from pyspark.sql.functions import (
    col, sum as _sum, count as _count, countDistinct, avg as _avg,
    max as _max, min as _min, datediff, current_date, current_timestamp,
    lit, when, to_date, months_between, floor as _floor, row_number,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np

# Try LightGBM first, fall back to sklearn GradientBoosting
try:
    import lightgbm as lgb
    USE_LIGHTGBM = True
    print("Using LightGBM classifier.")
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier
    USE_LIGHTGBM = False
    print("LightGBM not available — using sklearn GradientBoostingClassifier.")

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)
from sklearn.preprocessing import LabelEncoder
import mlflow
import mlflow.sklearn
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import seaborn as sns

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHURN_WINDOW_DAYS = 90
MIN_HISTORY_MONTHS = 6
TEST_SIZE = 0.20
RANDOM_STATE = 42
EXPERIMENT_NAME = "tt-churn-prediction"
MODEL_REGISTRY_NAME = "churn-predictor"

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

try:
    df_product = (
        spark.read.format("delta").table("dim_product")
        .filter(col("is_current") == True)
        .select("product_sk", "category")
    )
    print(f"  dim_product rows: {df_product.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_product table not found. Run gold notebooks first. Error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build Feature Set

# COMMAND ----------

print("Engineering churn features...")

# Parse date_key
df_sales_dated = df_sales.withColumn(
    "sale_date",
    to_date(col("date_key").cast("string"), "yyyyMMdd"),
)

# Per-customer aggregations
df_cust_features = (
    df_sales_dated
    .groupBy("customer_sk")
    .agg(
        _max("sale_date").alias("last_purchase_date"),
        _min("sale_date").alias("first_purchase_date"),
        _count("transaction_id").alias("purchase_frequency"),
        _avg("total_amount").alias("avg_order_value"),
        _sum("total_amount").alias("total_lifetime_spend"),
        _avg("discount_pct").alias("avg_discount_pct"),
        countDistinct("channel").alias("channel_count"),
    )
)

# Recency & tenure
df_cust_features = (
    df_cust_features
    .withColumn(
        "days_since_last_purchase",
        datediff(current_date(), col("last_purchase_date")),
    )
    .withColumn(
        "months_as_customer",
        _floor(months_between(current_date(), col("first_purchase_date"))),
    )
)

# Filter: only customers with 6+ months history
df_eligible = df_cust_features.filter(col("months_as_customer") >= MIN_HISTORY_MONTHS)
eligible_count = df_eligible.count()
total_count = df_cust_features.count()
print(f"  Total customers: {total_count:,}")
print(f"  Eligible (≥{MIN_HISTORY_MONTHS} months history): {eligible_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Add Behavioural Features

# COMMAND ----------

print("Adding behavioural features...")

# Category diversity
df_cat_div = (
    df_sales_dated
    .join(df_product, on="product_sk", how="left")
    .groupBy("customer_sk")
    .agg(countDistinct("category").alias("category_diversity"))
)

# Return rate proxy (high discount transactions)
df_return_rate = (
    df_sales
    .groupBy("customer_sk")
    .agg(
        _count(when(col("discount_pct") > 20, True)).alias("high_discount_count"),
        _count("*").alias("total_txn_count"),
    )
    .withColumn(
        "return_rate",
        col("high_discount_count").cast("double") / col("total_txn_count"),
    )
    .select("customer_sk", "return_rate")
)

# Preferred channel (mode)
window_ch = Window.partitionBy("customer_sk").orderBy(col("ch_count").desc())
df_pref_channel = (
    df_sales
    .groupBy("customer_sk", "channel")
    .agg(_count("*").alias("ch_count"))
    .withColumn("_rn", row_number().over(window_ch))
    .filter(col("_rn") == 1)
    .select("customer_sk", col("channel").alias("preferred_channel"))
)

# Join all features
df_full = (
    df_eligible
    .join(df_cat_div, on="customer_sk", how="left")
    .join(df_return_rate, on="customer_sk", how="left")
    .join(df_pref_channel, on="customer_sk", how="left")
    .join(
        df_customer.select(
            "customer_sk", "customer_id", "loyalty_tier", "is_active",
        ),
        on="customer_sk",
        how="inner",
    )
)

# Define churn label
df_labelled = df_full.withColumn(
    "is_churned",
    when(col("days_since_last_purchase") >= CHURN_WINDOW_DAYS, 1).otherwise(0),
)

print(f"  Feature set built: {df_labelled.count():,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Prepare Training Data

# COMMAND ----------

print("Preparing training data...")

FEATURE_COLS = [
    "days_since_last_purchase",
    "purchase_frequency",
    "avg_order_value",
    "total_lifetime_spend",
    "avg_discount_pct",
    "months_as_customer",
    "category_diversity",
    "return_rate",
    "channel_count",
]

CATEGORICAL_COLS = ["loyalty_tier", "preferred_channel"]

# Convert to Pandas
pdf = df_labelled.select(
    ["customer_sk", "customer_id", "is_churned"] + FEATURE_COLS + CATEGORICAL_COLS
).toPandas()

# Fill nulls
pdf[FEATURE_COLS] = pdf[FEATURE_COLS].fillna(0)
pdf[CATEGORICAL_COLS] = pdf[CATEGORICAL_COLS].fillna("Unknown")

# Encode categorical features
le_loyalty = LabelEncoder()
pdf["loyalty_tier_encoded"] = le_loyalty.fit_transform(pdf["loyalty_tier"])

le_channel = LabelEncoder()
pdf["preferred_channel_encoded"] = le_channel.fit_transform(pdf["preferred_channel"])

ML_FEATURES = FEATURE_COLS + ["loyalty_tier_encoded", "preferred_channel_encoded"]

X = pdf[ML_FEATURES].values
y = pdf["is_churned"].values

# Stratified train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
)

churn_rate = y.mean() * 100
print(f"  Total samples:  {len(y):,}")
print(f"  Churn rate:     {churn_rate:.1f}%")
print(f"  Train samples:  {len(y_train):,}")
print(f"  Test samples:   {len(y_test):,}")
print(f"  Features:       {len(ML_FEATURES)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Train Model with MLflow Tracking

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

print("Training churn prediction model...")
print("=" * 60)

with mlflow.start_run(run_name="churn-lgbm" if USE_LIGHTGBM else "churn-gbm"):
    mlflow.log_params({
        "algorithm": "LightGBM" if USE_LIGHTGBM else "GradientBoostingClassifier",
        "test_size": TEST_SIZE,
        "n_features": len(ML_FEATURES),
        "features": ", ".join(ML_FEATURES),
        "churn_window_days": CHURN_WINDOW_DAYS,
        "min_history_months": MIN_HISTORY_MONTHS,
        "n_train": len(y_train),
        "n_test": len(y_test),
        "churn_rate_pct": round(churn_rate, 2),
    })

    if USE_LIGHTGBM:
        model = lgb.LGBMClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=20,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            verbose=-1,
        )
    else:
        model = GradientBoostingClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            min_samples_leaf=20,
            random_state=RANDOM_STATE,
        )

    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    # Metrics
    auc = roc_auc_score(y_test, y_proba)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    mlflow.log_metrics({
        "auc": round(auc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "true_negatives": int(cm[0, 0]),
        "false_positives": int(cm[0, 1]),
        "false_negatives": int(cm[1, 0]),
        "true_positives": int(cm[1, 1]),
    })

    # Log model
    mlflow.sklearn.log_model(model, "model")
    run_id = mlflow.active_run().info.run_id

    print(f"  AUC:       {auc:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"\n  Confusion Matrix:")
    print(f"    TN={cm[0,0]:,}  FP={cm[0,1]:,}")
    print(f"    FN={cm[1,0]:,}  TP={cm[1,1]:,}")

print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Feature Importance

# COMMAND ----------

print("Generating feature importance plot...")

importances = model.feature_importances_
feat_imp = pd.DataFrame({
    "feature": ML_FEATURES,
    "importance": importances,
}).sort_values("importance", ascending=True)

fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(feat_imp["feature"], feat_imp["importance"], color="steelblue")
ax.set_xlabel("Feature Importance")
ax.set_title("Churn Prediction — Feature Importance", fontsize=13)
plt.tight_layout()
plt.savefig("/tmp/churn_feature_importance.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Feature importance plot rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Confusion Matrix Visualisation

# COMMAND ----------

fig, ax = plt.subplots(figsize=(7, 6))
sns.heatmap(
    cm, annot=True, fmt=",d", cmap="Blues",
    xticklabels=["Not Churned", "Churned"],
    yticklabels=["Not Churned", "Churned"],
    ax=ax,
)
ax.set_xlabel("Predicted")
ax.set_ylabel("Actual")
ax.set_title("Churn Prediction — Confusion Matrix", fontsize=13)
plt.tight_layout()
plt.savefig("/tmp/churn_confusion_matrix.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Confusion matrix rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Register Model

# COMMAND ----------

if run_id:
    model_uri = f"runs:/{run_id}/model"
    registered = mlflow.register_model(model_uri, MODEL_REGISTRY_NAME)
    print(f"✅ Registered model '{MODEL_REGISTRY_NAME}' version {registered.version}")
    print(f"   AUC: {auc:.4f}, F1: {f1:.4f}")
else:
    print("⚠ No run ID available — cannot register model.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Write Predictions to Gold Table

# COMMAND ----------

print("Writing churn predictions to ml_churn_predictions...")

# Score all eligible customers
X_all = pdf[ML_FEATURES].values
pdf["churn_probability"] = model.predict_proba(X_all)[:, 1]
pdf["churn_predicted"] = (pdf["churn_probability"] >= 0.5).astype(int)

df_predictions = spark.createDataFrame(
    pdf[["customer_sk", "customer_id", "churn_probability", "churn_predicted",
         "days_since_last_purchase", "purchase_frequency", "total_lifetime_spend",
         "loyalty_tier", "preferred_channel"]]
)
df_predictions = df_predictions.withColumn("_created_at", current_timestamp())

(
    df_predictions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("ml_churn_predictions")
)

row_count = df_predictions.count()
at_risk = pdf[pdf["churn_probability"] >= 0.5].shape[0]
print(f"✅ ml_churn_predictions written: {row_count:,} rows")
print(f"   Customers at risk (prob ≥ 0.5): {at_risk:,} ({at_risk/row_count*100:.1f}%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |---|---|
# MAGIC | Algorithm | LightGBM (or sklearn GBM fallback) |
# MAGIC | Churn definition | No purchase in 90 days (≥6 months history) |
# MAGIC | Split | 80/20 stratified |
# MAGIC | Evaluation metrics | AUC, Precision, Recall, F1, Confusion Matrix |
# MAGIC | Output table | `ml_churn_predictions` |
# MAGIC | MLflow experiment | `tt-churn-prediction` |
# MAGIC | Registered model | `churn-predictor` |

print("Churn prediction notebook complete.")
