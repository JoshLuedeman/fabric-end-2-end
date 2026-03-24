# Fabric notebook source
# MAGIC %md
# MAGIC # Data Science — Demand Forecasting
# MAGIC
# MAGIC **Purpose:** Predict next 30 days of sales by store × category using Facebook Prophet.
# MAGIC
# MAGIC **Business Context:** Contoso Global Retail uses demand forecasting to optimise
# MAGIC inventory replenishment, staffing, and promotional calendars. Accurate forecasts
# MAGIC reduce stock-outs (lost revenue) and overstock (markdowns). This notebook trains
# MAGIC one Prophet model per top-20 store×category combination, logs every run to MLflow,
# MAGIC and registers the best-performing model for downstream consumption.
# MAGIC
# MAGIC **Data Sources (Gold Layer):**
# MAGIC - `fact_sales` — transactional sales joined with surrogate keys
# MAGIC - `dim_store` — store attributes (store_id, store_name, region)
# MAGIC - `dim_product` — product attributes (category, subcategory)
# MAGIC
# MAGIC **Output:** `ml_demand_forecast` gold table + MLflow experiment
# MAGIC `contoso-demand-forecasting`

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install prophet lightgbm scikit-learn==1.5.2 matplotlib seaborn --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

from pyspark.sql.functions import (
    col, sum as _sum, count as _count, date_format, to_date, lit,
    current_timestamp, datediff, max as _max, min as _min, row_number,
)
from pyspark.sql.window import Window

import pandas as pd
import numpy as np
from prophet import Prophet
import mlflow
import mlflow.prophet
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FORECAST_HORIZON_DAYS = 30
TOP_N_COMBINATIONS = 20
TEST_DAYS = 30  # hold-out period for evaluation
EXPERIMENT_NAME = "contoso-demand-forecasting"
MODEL_REGISTRY_NAME = "demand-forecaster"

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
    df_store = (
        spark.read.format("delta").table("dim_store")
        .filter(col("is_current") == True)
        .select("store_sk", "store_id", "store_name", "region")
    )
    print(f"  dim_store rows:  {df_store.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_store table not found. Run gold notebooks first. Error: {e}")

try:
    df_product = (
        spark.read.format("delta").table("dim_product")
        .filter(col("is_current") == True)
        .select("product_sk", "product_id", "category")
    )
    print(f"  dim_product rows: {df_product.count():,}")
except Exception as e:
    raise RuntimeError(f"dim_product table not found. Run gold notebooks first. Error: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Aggregate Daily Sales by Store × Category

# COMMAND ----------

print("Building daily sales by store × category...")

# Join fact with dimensions
df_joined = (
    df_sales
    .join(df_store, on="store_sk", how="inner")
    .join(df_product, on="product_sk", how="inner")
)

# Parse date_key (integer YYYYMMDD) to date
df_joined = df_joined.withColumn(
    "sale_date",
    to_date(col("date_key").cast("string"), "yyyyMMdd"),
)

# Aggregate: daily revenue per store_id × category
df_daily = (
    df_joined
    .groupBy("store_id", "store_name", "category", "sale_date")
    .agg(
        _sum("total_amount").alias("daily_revenue"),
        _count("transaction_id").alias("daily_transactions"),
    )
    .orderBy("store_id", "category", "sale_date")
)

total_rows = df_daily.count()
print(f"  Daily aggregation rows: {total_rows:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Select Top-20 Store × Category Combinations by Revenue

# COMMAND ----------

print(f"Selecting top-{TOP_N_COMBINATIONS} store×category combinations...")

df_ranked = (
    df_daily
    .groupBy("store_id", "store_name", "category")
    .agg(_sum("daily_revenue").alias("total_revenue"))
    .orderBy(col("total_revenue").desc())
    .limit(TOP_N_COMBINATIONS)
)

top_combos = df_ranked.select("store_id", "category").collect()
print(f"  Selected {len(top_combos)} combinations for modelling.")

for i, row in enumerate(top_combos[:5]):
    print(f"    {i+1}. store={row['store_id']}, category={row['category']}")
if len(top_combos) > 5:
    print(f"    ... and {len(top_combos) - 5} more")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Train Prophet Models with MLflow Tracking

# COMMAND ----------

def calculate_metrics(actuals, predictions):
    """Calculate MAPE and RMSE between actual and predicted values."""
    mape = mean_absolute_percentage_error(actuals, predictions) * 100
    rmse = np.sqrt(mean_squared_error(actuals, predictions))
    return {"mape": round(mape, 4), "rmse": round(rmse, 4)}


mlflow.set_experiment(EXPERIMENT_NAME)

all_forecasts = []
best_run_id = None
best_mape = float("inf")

print(f"Training {len(top_combos)} Prophet models...")
print("=" * 60)

for combo in top_combos:
    store_id = combo["store_id"]
    category = combo["category"]

    # Filter to this store × category
    pdf = (
        df_daily
        .filter((col("store_id") == store_id) & (col("category") == category))
        .select(
            col("sale_date").alias("ds"),
            col("daily_revenue").alias("y"),
        )
        .orderBy("ds")
        .toPandas()
    )

    if len(pdf) < TEST_DAYS + 30:
        print(f"  ⚠ Skipping {store_id}/{category}: only {len(pdf)} days of data")
        continue

    # Train / test split
    cutoff = pdf["ds"].max() - pd.Timedelta(days=TEST_DAYS)
    train_df = pdf[pdf["ds"] <= cutoff].copy()
    test_df = pdf[pdf["ds"] > cutoff].copy()

    with mlflow.start_run(run_name=f"store_{store_id}_{category}"):
        mlflow.log_params({
            "store_id": store_id,
            "category": category,
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "forecast_horizon": FORECAST_HORIZON_DAYS,
        })

        # Train Prophet model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        model.fit(train_df)

        # Evaluate on test set
        future_test = model.make_future_dataframe(periods=len(test_df))
        forecast_test = model.predict(future_test)
        pred_test = forecast_test[forecast_test["ds"].isin(test_df["ds"])]

        metrics = calculate_metrics(
            test_df["y"].values,
            pred_test["yhat"].values[:len(test_df)],
        )
        mlflow.log_metrics({"mape": metrics["mape"], "rmse": metrics["rmse"]})

        # Generate future forecast (next 30 days)
        future_df = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS)
        forecast = model.predict(future_df)
        future_only = forecast.tail(FORECAST_HORIZON_DAYS)[
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ].copy()
        future_only["store_id"] = store_id
        future_only["category"] = category
        all_forecasts.append(future_only)

        # Log model artifact
        mlflow.prophet.log_model(model, "model")

        # Track best model
        if metrics["mape"] < best_mape:
            best_mape = metrics["mape"]
            best_run_id = mlflow.active_run().info.run_id

        print(
            f"  ✅ {store_id} / {category}: "
            f"MAPE={metrics['mape']:.2f}%, RMSE={metrics['rmse']:.2f}"
        )

print("=" * 60)
print(f"Training complete. Best MAPE: {best_mape:.2f}%")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Register Best Model

# COMMAND ----------

if best_run_id:
    model_uri = f"runs:/{best_run_id}/model"
    registered = mlflow.register_model(model_uri, MODEL_REGISTRY_NAME)
    print(f"✅ Registered model '{MODEL_REGISTRY_NAME}' version {registered.version}")
    print(f"   Source run: {best_run_id}")
    print(f"   Best MAPE:  {best_mape:.2f}%")
else:
    print("⚠ No models trained — cannot register.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Write Forecasts to Gold Table

# COMMAND ----------

if all_forecasts:
    print("Writing forecasts to ml_demand_forecast...")

    pdf_all = pd.concat(all_forecasts, ignore_index=True)
    pdf_all.rename(columns={
        "ds": "forecast_date",
        "yhat": "predicted_revenue",
        "yhat_lower": "predicted_lower",
        "yhat_upper": "predicted_upper",
    }, inplace=True)

    df_forecast = spark.createDataFrame(pdf_all)
    df_forecast = df_forecast.withColumn("_created_at", current_timestamp())

    (
        df_forecast
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable("ml_demand_forecast")
    )

    row_count = df_forecast.count()
    print(f"✅ ml_demand_forecast written: {row_count:,} rows")
else:
    print("⚠ No forecasts generated — skipping table write.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Visualisation — Actual vs Predicted (Sample Stores)

# COMMAND ----------

if top_combos:
    sample_combos = top_combos[:4]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    axes = axes.flatten()

    for idx, combo in enumerate(sample_combos):
        store_id = combo["store_id"]
        category = combo["category"]

        pdf_hist = (
            df_daily
            .filter((col("store_id") == store_id) & (col("category") == category))
            .select(col("sale_date").alias("ds"), col("daily_revenue").alias("y"))
            .orderBy("ds")
            .toPandas()
        )

        ax = axes[idx]
        ax.plot(pdf_hist["ds"], pdf_hist["y"], label="Actual", alpha=0.7, linewidth=0.8)

        # Overlay forecast if available
        for fc in all_forecasts:
            if fc["store_id"].iloc[0] == store_id and fc["category"].iloc[0] == category:
                ax.plot(
                    fc["ds"], fc["yhat"],
                    label="Forecast", color="red", linewidth=1.5,
                )
                ax.fill_between(
                    fc["ds"], fc["yhat_lower"], fc["yhat_upper"],
                    alpha=0.2, color="red", label="95% CI",
                )
                break

        ax.set_title(f"{store_id} — {category}", fontsize=10)
        ax.set_xlabel("Date")
        ax.set_ylabel("Daily Revenue ($)")
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=30)

    plt.suptitle("Demand Forecast — Actual vs Predicted (Top 4 Combinations)", fontsize=13)
    plt.tight_layout()
    plt.savefig("/tmp/demand_forecast_viz.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✅ Visualisation rendered.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Summary
# MAGIC
# MAGIC | Metric | Value |
# MAGIC |---|---|
# MAGIC | Models trained | Top-20 store × category combinations |
# MAGIC | Algorithm | Facebook Prophet |
# MAGIC | Forecast horizon | 30 days |
# MAGIC | Evaluation metric | MAPE, RMSE |
# MAGIC | Output table | `ml_demand_forecast` |
# MAGIC | MLflow experiment | `contoso-demand-forecasting` |
# MAGIC | Registered model | `demand-forecaster` |

print("Demand forecasting notebook complete.")
