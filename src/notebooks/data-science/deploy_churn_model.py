# Fabric notebook source
# MAGIC %md
# MAGIC # Deploy Churn Prediction Model
# MAGIC
# MAGIC **Purpose:** Load the best churn prediction model from the MLflow model
# MAGIC registry, deploy it as a Fabric ML Model, run nightly batch scoring
# MAGIC across the entire customer base, and output a `churn_risk_scores` table
# MAGIC in the gold Lakehouse.
# MAGIC
# MAGIC **Business Context:** The Contoso retention team needs a daily-refreshed
# MAGIC churn risk table so they can trigger win-back campaigns within 24 hours
# MAGIC of a customer showing elevated churn risk. This notebook operationalises
# MAGIC the model trained in `churn_prediction.py`.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `churn_prediction.py` has been run and `churn-predictor` registered in MLflow
# MAGIC - Gold lakehouse tables (`fact_sales`, `dim_customer`, `dim_product`) exist

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install lightgbm scikit-learn==1.5.2 mlflow --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from pyspark.sql.functions import (
    col, sum as _sum, count as _count, countDistinct, avg as _avg,
    max as _max, min as _min, datediff, current_date, current_timestamp,
    lit, when, to_date, months_between, floor as _floor, row_number,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_NAME = "contoso-churn-prediction"
MODEL_REGISTRY_NAME = "churn-predictor"
CHURN_WINDOW_DAYS = 90
MIN_HISTORY_MONTHS = 6
OUTPUT_TABLE = "churn_risk_scores"
RISK_THRESHOLD_HIGH = 0.7
RISK_THRESHOLD_MEDIUM = 0.4

# Feature columns must match the training notebook
ML_FEATURES = [
    "days_since_last_purchase",
    "purchase_frequency",
    "avg_order_value",
    "total_lifetime_spend",
    "unique_categories",
    "preferred_channel_encoded",
    "loyalty_tier_encoded",
    "months_as_customer",
    "purchase_trend",
    "avg_days_between_purchases",
]

print("Imports and configuration loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load Best Model from MLflow Registry

# COMMAND ----------

client = MlflowClient()

model_name = MODEL_REGISTRY_NAME
try:
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise RuntimeError(f"No versions found for model '{model_name}'. Run churn_prediction.py first.")

    # Prefer Production stage, then latest by version number
    prod_versions = [v for v in versions if v.current_stage == "Production"]
    if prod_versions:
        model_version = prod_versions[0]
        print(f"✅ Found Production model: {model_name} v{model_version.version}")
    else:
        model_version = sorted(versions, key=lambda v: int(v.version), reverse=True)[0]
        print(f"✅ Found latest model: {model_name} v{model_version.version} (stage: {model_version.current_stage})")

    model_uri = f"models:/{model_name}/{model_version.version}"

except Exception as e:
    print(f"⚠ Registry lookup failed: {e}")
    print("  Falling back to latest experiment run...")
    mlflow.set_experiment(EXPERIMENT_NAME)
    runs = mlflow.search_runs(order_by=["metrics.auc DESC"], max_results=1)
    if runs.empty:
        raise RuntimeError("No MLflow runs found. Run churn_prediction.py first.")
    run_id = runs.iloc[0]["run_id"]
    model_uri = f"runs:/{run_id}/model"
    print(f"   Using run: {run_id}")

# Load the model
model = mlflow.sklearn.load_model(model_uri)
print(f"✅ Model loaded: {type(model).__name__}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Register / Update Fabric ML Model

# COMMAND ----------

registered_model = mlflow.register_model(
    model_uri=model_uri,
    name=MODEL_REGISTRY_NAME,
)
print(f"✅ Model registered: {MODEL_REGISTRY_NAME} v{registered_model.version}")

client.transition_model_version_stage(
    name=MODEL_REGISTRY_NAME,
    version=registered_model.version,
    stage="Production",
    archive_existing_versions=True,
)
print(f"   Transitioned v{registered_model.version} to Production stage.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Build Feature Matrix for All Customers
# MAGIC
# MAGIC Replicate the exact feature engineering from `churn_prediction.py` to
# MAGIC ensure consistency between training and scoring.

# COMMAND ----------

print("Reading gold layer tables...")

df_sales = spark.read.format("delta").table("fact_sales")
df_customers = spark.read.format("delta").table("dim_customer")
df_products = spark.read.format("delta").table("dim_product")

print(f"  fact_sales:    {df_sales.count():,} rows")
print(f"  dim_customer:  {df_customers.count():,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a. Customer-Level Feature Engineering

# COMMAND ----------

from sklearn.preprocessing import LabelEncoder

# Join sales with product for category info
df_enriched = df_sales.join(df_products, on="product_sk", how="left")

# Aggregate to customer level
df_features = (
    df_enriched
    .groupBy("customer_sk")
    .agg(
        _max("sale_date").alias("last_purchase_date"),
        _min("sale_date").alias("first_purchase_date"),
        _count("*").alias("purchase_frequency"),
        _avg("total_amount").alias("avg_order_value"),
        _sum("total_amount").alias("total_lifetime_spend"),
        countDistinct("category").alias("unique_categories"),
    )
)

# Calculate derived features
df_features = (
    df_features
    .withColumn("days_since_last_purchase",
                datediff(current_date(), col("last_purchase_date")))
    .withColumn("months_as_customer",
                months_between(current_date(), col("first_purchase_date")).cast("int"))
    .withColumn("avg_days_between_purchases",
                when(col("purchase_frequency") > 1,
                     datediff(col("last_purchase_date"), col("first_purchase_date")) / (col("purchase_frequency") - 1))
                .otherwise(lit(0.0)))
)

# Filter to customers with enough history
df_features = df_features.filter(col("months_as_customer") >= MIN_HISTORY_MONTHS)

# Join customer attributes
df_features = df_features.join(
    df_customers.select("customer_sk", "customer_id", "loyalty_tier",
                        "preferred_channel", "customer_name", "email"),
    on="customer_sk",
    how="left",
)

print(f"✅ Feature matrix built: {df_features.count():,} eligible customers")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Encode Categorical Features

# COMMAND ----------

# Convert to pandas for sklearn scoring
pdf = df_features.toPandas()

# Purchase trend: ratio of recent vs older purchases (simplified)
pdf["purchase_trend"] = np.where(
    pdf["avg_days_between_purchases"] > 0,
    pdf["days_since_last_purchase"] / pdf["avg_days_between_purchases"],
    1.0,
)

# Encode categoricals (same approach as training notebook)
le_channel = LabelEncoder()
pdf["preferred_channel_encoded"] = le_channel.fit_transform(
    pdf["preferred_channel"].fillna("Unknown")
)

le_loyalty = LabelEncoder()
pdf["loyalty_tier_encoded"] = le_loyalty.fit_transform(
    pdf["loyalty_tier"].fillna("Unknown")
)

print(f"✅ Features encoded. Shape: {pdf.shape}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Batch Scoring — Score All Customers

# COMMAND ----------

print(f"Scoring {len(pdf):,} customers...")

X = pdf[ML_FEATURES].values

# Get probability of churn (class 1)
churn_probabilities = model.predict_proba(X)[:, 1]
churn_predictions = (churn_probabilities >= 0.5).astype(int)

# Add scores to dataframe
pdf["churn_probability"] = churn_probabilities
pdf["churn_predicted"] = churn_predictions

# Assign risk tiers
pdf["risk_tier"] = np.where(
    pdf["churn_probability"] >= RISK_THRESHOLD_HIGH, "High",
    np.where(pdf["churn_probability"] >= RISK_THRESHOLD_MEDIUM, "Medium", "Low")
)

# Summary
high_risk = (pdf["risk_tier"] == "High").sum()
medium_risk = (pdf["risk_tier"] == "Medium").sum()
low_risk = (pdf["risk_tier"] == "Low").sum()
print(f"✅ Scoring complete:")
print(f"   High risk:   {high_risk:,} ({high_risk/len(pdf)*100:.1f}%)")
print(f"   Medium risk: {medium_risk:,} ({medium_risk/len(pdf)*100:.1f}%)")
print(f"   Low risk:    {low_risk:,} ({low_risk/len(pdf)*100:.1f}%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Write Churn Risk Scores to Gold Lakehouse

# COMMAND ----------

output_columns = [
    "customer_sk", "customer_id", "customer_name", "email",
    "churn_probability", "churn_predicted", "risk_tier",
    "days_since_last_purchase", "purchase_frequency",
    "total_lifetime_spend", "avg_order_value",
    "loyalty_tier", "preferred_channel",
]

df_scores = spark.createDataFrame(pdf[output_columns])
df_scores = (
    df_scores
    .withColumn("_scored_at", current_timestamp())
    .withColumn("_model_version", lit(str(registered_model.version)))
    .withColumn("_model_name", lit(MODEL_REGISTRY_NAME))
)

(
    df_scores
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(OUTPUT_TABLE)
)

row_count = df_scores.count()
print(f"✅ {OUTPUT_TABLE} written: {row_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. SynapseML PREDICT Integration (Batch Scoring)
# MAGIC
# MAGIC For production nightly batch scoring without loading the model into
# MAGIC Python, use SynapseML PREDICT:
# MAGIC
# MAGIC ```python
# MAGIC from synapse.ml.predict import MLFlowTransformer
# MAGIC
# MAGIC model = MLFlowTransformer(
# MAGIC     inputCols=["days_since_last_purchase", "purchase_frequency",
# MAGIC                "avg_order_value", "total_lifetime_spend",
# MAGIC                "unique_categories", "preferred_channel_encoded",
# MAGIC                "loyalty_tier_encoded", "months_as_customer",
# MAGIC                "purchase_trend", "avg_days_between_purchases"],
# MAGIC     outputCol="churn_probability",
# MAGIC     modelName="churn-predictor",
# MAGIC     modelVersion=<latest_version>,
# MAGIC )
# MAGIC
# MAGIC df_features = spark.read.format("delta").table("customer_features_daily")
# MAGIC df_scored = model.transform(df_features)
# MAGIC df_scored.write.format("delta").mode("overwrite").saveAsTable("churn_risk_scores")
# MAGIC ```
# MAGIC
# MAGIC Schedule this as a Fabric Data Pipeline activity that runs nightly
# MAGIC after the gold layer refresh completes.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Log Deployment Metrics to MLflow

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

with mlflow.start_run(run_name=f"batch-scoring-{datetime.now().strftime('%Y%m%d')}"):
    mlflow.log_param("model_name", MODEL_REGISTRY_NAME)
    mlflow.log_param("model_version", str(registered_model.version))
    mlflow.log_param("scoring_date", datetime.now().isoformat())
    mlflow.log_param("output_table", OUTPUT_TABLE)
    mlflow.log_metric("total_customers_scored", len(pdf))
    mlflow.log_metric("high_risk_count", int(high_risk))
    mlflow.log_metric("medium_risk_count", int(medium_risk))
    mlflow.log_metric("low_risk_count", int(low_risk))
    mlflow.log_metric("high_risk_pct", high_risk / len(pdf) * 100)
    mlflow.log_metric("avg_churn_probability", float(pdf["churn_probability"].mean()))
    print("✅ Deployment metrics logged to MLflow.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Summary
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Source model | `churn-predictor` (MLflow) |
# MAGIC | Serving method | Batch scoring (nightly) + SynapseML PREDICT |
# MAGIC | Output table | `churn_risk_scores` (gold Lakehouse) |
# MAGIC | Risk tiers | High (≥0.7), Medium (≥0.4), Low (<0.4) |
# MAGIC | Schedule | Nightly, after gold layer refresh |
# MAGIC | Consumers | Retention team dashboard, CRM integration |

print("Churn model deployment notebook complete.")
