# Fabric notebook source
# MAGIC %md
# MAGIC # Deploy Demand Forecasting Model
# MAGIC
# MAGIC **Purpose:** Load the best demand forecasting model from the MLflow model
# MAGIC registry, register it as a Fabric ML Model, create a scoring endpoint,
# MAGIC and run a test prediction.
# MAGIC
# MAGIC **Business Context:** Tales & Timber needs real-time demand
# MAGIC predictions surfaced in Power BI dashboards and operational systems.
# MAGIC This notebook bridges the gap between model training (see
# MAGIC `demand_forecasting.py`) and production serving.
# MAGIC
# MAGIC **Serving Approach:**
# MAGIC - Primary: Fabric ML Model + SynapseML PREDICT for batch/DirectQuery
# MAGIC - Fallback: MLflow model loaded in-notebook for ad-hoc scoring
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `demand_forecasting.py` has been run and a model registered as
# MAGIC   `demand-forecaster` in MLflow
# MAGIC - Gold lakehouse tables (`fact_sales`, `dim_store`, `dim_product`) exist

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install prophet mlflow scikit-learn==1.5.2 --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

import mlflow
import mlflow.prophet
from mlflow.tracking import MlflowClient

from pyspark.sql.functions import (
    col, lit, current_timestamp, struct, to_date,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, DateType,
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXPERIMENT_NAME = "tt-demand-forecasting"
MODEL_REGISTRY_NAME = "demand-forecaster"
GOLD_LAKEHOUSE = "lh_gold"
ENDPOINT_NAME = "demand-forecast-endpoint"
FORECAST_HORIZON_DAYS = 30

print("Imports and configuration loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load Best Model from MLflow Registry

# COMMAND ----------

client = MlflowClient()

# Get the latest version in "Production" stage, fall back to latest version
model_name = MODEL_REGISTRY_NAME
model_version = None

try:
    # Search for versions with Production alias/stage
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise RuntimeError(f"No versions found for model '{model_name}'. Run demand_forecasting.py first.")

    # Prefer Production stage, then latest by version number
    prod_versions = [v for v in versions if v.current_stage == "Production"]
    if prod_versions:
        model_version = prod_versions[0]
        print(f"✅ Found Production model: {model_name} v{model_version.version}")
    else:
        # Take the latest version
        model_version = sorted(versions, key=lambda v: int(v.version), reverse=True)[0]
        print(f"✅ Found latest model: {model_name} v{model_version.version} (stage: {model_version.current_stage})")

    model_uri = f"models:/{model_name}/{model_version.version}"
    print(f"   Model URI: {model_uri}")

except Exception as e:
    print(f"⚠ Error loading model: {e}")
    print("  Falling back to latest run in experiment...")
    mlflow.set_experiment(EXPERIMENT_NAME)
    runs = mlflow.search_runs(order_by=["metrics.mape ASC"], max_results=1)
    if runs.empty:
        raise RuntimeError("No MLflow runs found. Run demand_forecasting.py first.")
    run_id = runs.iloc[0]["run_id"]
    model_uri = f"runs:/{run_id}/model"
    print(f"   Using run: {run_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Register as Fabric ML Model
# MAGIC
# MAGIC Fabric ML Models are the native model registry that integrates with
# MAGIC SynapseML PREDICT and Power BI DirectQuery. When a model is registered
# MAGIC here, it becomes available for:
# MAGIC - Batch scoring via `spark.read.predict()`
# MAGIC - Real-time scoring via PREDICT T-SQL function
# MAGIC - Power BI DirectQuery integration

# COMMAND ----------

# Register or update the model in the Fabric-native registry.
# If the Terraform module has already created the ML Model container,
# this call populates it with the latest trained version.
registered_model = mlflow.register_model(
    model_uri=model_uri,
    name=MODEL_REGISTRY_NAME,
)
print(f"✅ Model registered: {MODEL_REGISTRY_NAME} v{registered_model.version}")

# Transition to Production stage
client.transition_model_version_stage(
    name=MODEL_REGISTRY_NAME,
    version=registered_model.version,
    stage="Production",
    archive_existing_versions=True,
)
print(f"   Transitioned v{registered_model.version} to Production stage.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Load Model for Scoring

# COMMAND ----------

# Load the Prophet model from the registry
loaded_model = mlflow.prophet.load_model(f"models:/{MODEL_REGISTRY_NAME}/Production")
print(f"✅ Model loaded for scoring: {type(loaded_model).__name__}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Test Scoring — Sample Prediction

# COMMAND ----------

# Create a future dataframe for the next FORECAST_HORIZON_DAYS days
today = datetime.today()
future_dates = pd.DataFrame({
    "ds": pd.date_range(start=today, periods=FORECAST_HORIZON_DAYS, freq="D"),
})

# Run prediction
forecast = loaded_model.predict(future_dates)

# Display results
print(f"✅ Test prediction complete — {len(forecast)} days forecast generated")
print(f"\nSample forecast (next 7 days):")
print(forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].head(7).to_string(index=False))

# Validate predictions are reasonable
assert forecast["yhat"].notna().all(), "Forecast contains NaN values"
assert (forecast["yhat"] >= 0).all(), "Forecast contains negative values"
print("\n✅ Prediction validation passed (no NaN, no negatives)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Batch Scoring — Full Store × Category Forecast

# COMMAND ----------

# Read gold layer for store × category combinations
try:
    df_stores = spark.read.format("delta").table("dim_store").select("store_id", "store_name").distinct()
    df_products = spark.read.format("delta").table("dim_product").select("category").distinct()

    stores = [row["store_id"] for row in df_stores.collect()]
    categories = [row["category"] for row in df_products.collect()]

    print(f"Generating forecasts for {len(stores)} stores × {len(categories)} categories...")

    # Score all combinations (simplified: uses the single global model)
    # In production, load per-combination models from MLflow
    all_forecasts = []
    for store_id in stores[:5]:  # Limit to top-5 for demo
        for category in categories[:4]:  # Limit to top-4 for demo
            fc = loaded_model.predict(future_dates)
            fc["store_id"] = store_id
            fc["category"] = category
            all_forecasts.append(fc[["ds", "store_id", "category", "yhat", "yhat_lower", "yhat_upper"]])

    df_forecast_pd = pd.concat(all_forecasts, ignore_index=True)
    df_forecast_spark = spark.createDataFrame(df_forecast_pd)
    df_forecast_spark = df_forecast_spark.withColumn("_scored_at", current_timestamp())

    # Write to gold lakehouse
    (
        df_forecast_spark
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable("ml_demand_forecast_serving")
    )

    row_count = df_forecast_spark.count()
    print(f"✅ ml_demand_forecast_serving written: {row_count:,} rows")

except Exception as e:
    print(f"⚠ Batch scoring skipped (gold tables may not exist): {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. SynapseML PREDICT Integration
# MAGIC
# MAGIC SynapseML PREDICT enables scoring directly in Spark SQL without loading
# MAGIC the model into a Python process. This is the recommended approach for
# MAGIC production batch scoring and Power BI DirectQuery.
# MAGIC
# MAGIC ### Batch Scoring with PREDICT
# MAGIC
# MAGIC ```python
# MAGIC from synapse.ml.predict import MLFlowTransformer
# MAGIC
# MAGIC model = MLFlowTransformer(
# MAGIC     inputCols=["ds"],
# MAGIC     outputCol="prediction",
# MAGIC     modelName="demand-forecaster",
# MAGIC     modelVersion=<latest_version>,
# MAGIC )
# MAGIC
# MAGIC df_input = spark.read.format("delta").table("scoring_input")
# MAGIC df_scored = model.transform(df_input)
# MAGIC df_scored.write.format("delta").mode("overwrite").saveAsTable("ml_demand_forecast_live")
# MAGIC ```
# MAGIC
# MAGIC ### Power BI DirectQuery Integration
# MAGIC
# MAGIC To enable real-time predictions in Power BI:
# MAGIC
# MAGIC 1. Create a SQL view in the Fabric Warehouse that calls PREDICT:
# MAGIC    ```sql
# MAGIC    CREATE VIEW vw_demand_forecast_live AS
# MAGIC    SELECT
# MAGIC        store_id,
# MAGIC        category,
# MAGIC        forecast_date,
# MAGIC        PREDICT('demand-forecaster', forecast_date) AS predicted_revenue,
# MAGIC        GETDATE() AS _scored_at
# MAGIC    FROM dbo.forecast_input_dates
# MAGIC    CROSS JOIN dbo.store_category_combinations;
# MAGIC    ```
# MAGIC
# MAGIC 2. Connect Power BI to the warehouse view using DirectQuery mode.
# MAGIC    Each dashboard refresh triggers a fresh prediction.
# MAGIC
# MAGIC 3. Add a visual-level filter for store/category to enable drill-down
# MAGIC    forecasting in the Tales & Timber Retail dashboard.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Summary
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Source model | `demand-forecaster` (MLflow) |
# MAGIC | Serving method | SynapseML PREDICT / batch scoring |
# MAGIC | Output table | `ml_demand_forecast_serving` |
# MAGIC | Forecast horizon | 30 days |
# MAGIC | Power BI integration | DirectQuery via warehouse PREDICT view |
# MAGIC | Refresh schedule | Daily (orchestrated by data pipeline) |

print("Demand model deployment notebook complete.")
