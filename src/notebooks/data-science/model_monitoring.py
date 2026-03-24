# Fabric notebook source
# MAGIC %md
# MAGIC # ML Model Monitoring — ModelOps
# MAGIC
# MAGIC **Purpose:** Monitor deployed ML models for data drift, prediction drift,
# MAGIC and performance degradation. Generate model health reports and trigger
# MAGIC retraining when drift exceeds thresholds.
# MAGIC
# MAGIC **Business Context:** Tales & Timber's ML models (demand forecasting,
# MAGIC churn prediction) are retrained periodically, but the underlying data
# MAGIC distributions can shift between retraining cycles due to seasonality,
# MAGIC promotions, or market changes. This notebook detects drift early so the
# MAGIC data science team can act before model accuracy degrades.
# MAGIC
# MAGIC **Models Monitored:**
# MAGIC - `demand-forecaster` — Prophet-based demand forecasting
# MAGIC - `churn-predictor` — LightGBM/GBM churn prediction
# MAGIC
# MAGIC **Metrics Tracked:**
# MAGIC - Feature drift (PSI — Population Stability Index)
# MAGIC - Prediction distribution shift (KS test)
# MAGIC - Model performance vs baseline (MAPE for regression, AUC for classification)
# MAGIC
# MAGIC **Schedule:** Run daily as part of the MLOps pipeline.

# MAGIC %md
# MAGIC ## 0. Install Dependencies

# COMMAND ----------

%pip install scikit-learn==1.5.2 scipy mlflow --quiet

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports & Configuration

# COMMAND ----------

import warnings
warnings.filterwarnings("ignore")

import mlflow
from mlflow.tracking import MlflowClient

from pyspark.sql.functions import (
    col, count as _count, avg as _avg, stddev, min as _min,
    max as _max, current_timestamp, lit, when,
)

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODELS_TO_MONITOR = {
    "demand-forecaster": {
        "experiment": "tt-demand-forecasting",
        "type": "regression",
        "primary_metric": "mape",
        "threshold_metric": 0.25,       # MAPE > 25% triggers alert
        "prediction_table": "ml_demand_forecast_serving",
        "baseline_table": "ml_demand_forecast",
    },
    "churn-predictor": {
        "experiment": "tt-churn-prediction",
        "type": "classification",
        "primary_metric": "auc",
        "threshold_metric": 0.70,       # AUC < 0.70 triggers alert
        "prediction_table": "churn_risk_scores",
        "baseline_table": "ml_churn_predictions",
    },
}

# Drift thresholds
PSI_THRESHOLD = 0.20          # PSI > 0.2 = significant drift
KS_PVALUE_THRESHOLD = 0.01   # KS p-value < 0.01 = significant shift
MONITORING_EXPERIMENT = "tt-model-monitoring"

print("Imports and configuration loaded.")
print(f"Monitoring {len(MODELS_TO_MONITOR)} models: {', '.join(MODELS_TO_MONITOR.keys())}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Drift Detection Utilities

# COMMAND ----------

def calculate_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """
    Calculate Population Stability Index (PSI) between two distributions.

    PSI < 0.1:  No significant drift
    PSI 0.1-0.2: Moderate drift — monitor closely
    PSI > 0.2:  Significant drift — investigate / retrain

    Parameters
    ----------
    expected : np.ndarray
        Baseline (training) distribution.
    actual : np.ndarray
        Current (production) distribution.
    bins : int
        Number of bins for discretisation.

    Returns
    -------
    float
        PSI value.
    """
    # Create bins from expected distribution
    breakpoints = np.linspace(
        min(expected.min(), actual.min()),
        max(expected.max(), actual.max()),
        bins + 1,
    )

    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]

    # Avoid division by zero
    expected_pct = (expected_counts + 1) / (expected_counts.sum() + bins)
    actual_pct = (actual_counts + 1) / (actual_counts.sum() + bins)

    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi)


def ks_test(expected: np.ndarray, actual: np.ndarray) -> dict:
    """
    Kolmogorov-Smirnov test for distribution shift.

    Returns
    -------
    dict with 'statistic' and 'pvalue'.
    """
    stat, pvalue = stats.ks_2samp(expected, actual)
    return {"statistic": float(stat), "pvalue": float(pvalue)}


def assess_drift_level(psi: float) -> str:
    """Categorise drift severity."""
    if psi < 0.1:
        return "None"
    elif psi < 0.2:
        return "Moderate"
    else:
        return "Significant"

print("✅ Drift detection utilities loaded.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Feature Drift Analysis

# COMMAND ----------

client = MlflowClient()
monitoring_results = []

for model_name, config in MODELS_TO_MONITOR.items():
    print(f"\n{'='*60}")
    print(f"  Monitoring: {model_name}")
    print(f"{'='*60}")

    try:
        # ---------------------------------------------------------------
        # 3a. Load baseline and current prediction data
        # ---------------------------------------------------------------
        try:
            df_baseline = spark.read.format("delta").table(config["baseline_table"])
            df_current = spark.read.format("delta").table(config["prediction_table"])
        except Exception as e:
            print(f"  ⚠ Cannot load tables for {model_name}: {e}")
            monitoring_results.append({
                "model_name": model_name,
                "status": "ERROR",
                "error": str(e),
                "checked_at": datetime.now().isoformat(),
            })
            continue

        baseline_count = df_baseline.count()
        current_count = df_current.count()
        print(f"  Baseline rows: {baseline_count:,}")
        print(f"  Current rows:  {current_count:,}")

        # ---------------------------------------------------------------
        # 3b. Feature drift (PSI) on numeric columns
        # ---------------------------------------------------------------
        numeric_cols = [
            f.name for f in df_current.schema.fields
            if f.dataType.typeName() in ("double", "float", "integer", "long")
            and not f.name.startswith("_")
        ]

        feature_drift = {}
        for col_name in numeric_cols[:10]:  # Limit to top-10 features
            try:
                baseline_vals = np.array(
                    df_baseline.select(col_name).dropna().limit(10000).toPandas()[col_name]
                )
                current_vals = np.array(
                    df_current.select(col_name).dropna().limit(10000).toPandas()[col_name]
                )

                if len(baseline_vals) < 50 or len(current_vals) < 50:
                    continue

                psi = calculate_psi(baseline_vals, current_vals)
                ks = ks_test(baseline_vals, current_vals)
                drift_level = assess_drift_level(psi)

                feature_drift[col_name] = {
                    "psi": round(psi, 4),
                    "ks_statistic": round(ks["statistic"], 4),
                    "ks_pvalue": round(ks["pvalue"], 6),
                    "drift_level": drift_level,
                }

                flag = "🔴" if drift_level == "Significant" else ("🟡" if drift_level == "Moderate" else "🟢")
                print(f"  {flag} {col_name}: PSI={psi:.4f} ({drift_level})")

            except Exception as e:
                print(f"  ⚠ Skipping {col_name}: {e}")

        # ---------------------------------------------------------------
        # 3c. Prediction distribution shift
        # ---------------------------------------------------------------
        pred_col = "churn_probability" if config["type"] == "classification" else "yhat"
        prediction_drift = {}

        try:
            baseline_preds = np.array(
                df_baseline.select(pred_col).dropna().limit(10000).toPandas()[pred_col]
            )
            current_preds = np.array(
                df_current.select(pred_col).dropna().limit(10000).toPandas()[pred_col]
            )

            pred_psi = calculate_psi(baseline_preds, current_preds)
            pred_ks = ks_test(baseline_preds, current_preds)

            prediction_drift = {
                "psi": round(pred_psi, 4),
                "ks_statistic": round(pred_ks["statistic"], 4),
                "ks_pvalue": round(pred_ks["pvalue"], 6),
                "drift_level": assess_drift_level(pred_psi),
                "baseline_mean": round(float(baseline_preds.mean()), 4),
                "current_mean": round(float(current_preds.mean()), 4),
            }

            flag = "🔴" if prediction_drift["drift_level"] == "Significant" else "🟢"
            print(f"\n  {flag} Prediction drift: PSI={pred_psi:.4f} ({prediction_drift['drift_level']})")
            print(f"     Baseline mean: {prediction_drift['baseline_mean']:.4f}")
            print(f"     Current mean:  {prediction_drift['current_mean']:.4f}")

        except Exception as e:
            print(f"  ⚠ Prediction drift check failed: {e}")

        # ---------------------------------------------------------------
        # 3d. Model performance vs baseline
        # ---------------------------------------------------------------
        performance = {}
        try:
            versions = client.search_model_versions(f"name='{model_name}'")
            if versions:
                latest = sorted(versions, key=lambda v: int(v.version), reverse=True)[0]
                run = client.get_run(latest.run_id)
                metric_val = run.data.metrics.get(config["primary_metric"], None)

                if metric_val is not None:
                    performance = {
                        "metric_name": config["primary_metric"],
                        "metric_value": round(metric_val, 4),
                        "threshold": config["threshold_metric"],
                        "model_version": latest.version,
                    }

                    if config["type"] == "regression":
                        # For regression, lower is better (MAPE)
                        is_degraded = metric_val > config["threshold_metric"]
                    else:
                        # For classification, higher is better (AUC)
                        is_degraded = metric_val < config["threshold_metric"]

                    performance["is_degraded"] = is_degraded
                    flag = "🔴" if is_degraded else "🟢"
                    print(f"\n  {flag} Performance: {config['primary_metric']}={metric_val:.4f} (threshold: {config['threshold_metric']})")

        except Exception as e:
            print(f"  ⚠ Performance check failed: {e}")

        # ---------------------------------------------------------------
        # 3e. Determine overall health and retraining recommendation
        # ---------------------------------------------------------------
        has_feature_drift = any(
            d["drift_level"] == "Significant" for d in feature_drift.values()
        )
        has_prediction_drift = prediction_drift.get("drift_level") == "Significant"
        has_performance_degradation = performance.get("is_degraded", False)

        needs_retraining = has_feature_drift or has_prediction_drift or has_performance_degradation

        if needs_retraining:
            overall_status = "RETRAIN_RECOMMENDED"
            reasons = []
            if has_feature_drift:
                drifted = [k for k, v in feature_drift.items() if v["drift_level"] == "Significant"]
                reasons.append(f"Feature drift in: {', '.join(drifted)}")
            if has_prediction_drift:
                reasons.append(f"Prediction distribution shifted (PSI={prediction_drift['psi']:.4f})")
            if has_performance_degradation:
                reasons.append(f"Performance degraded: {config['primary_metric']}={performance['metric_value']:.4f}")
            print(f"\n  🔴 RETRAINING RECOMMENDED:")
            for r in reasons:
                print(f"     - {r}")
        else:
            overall_status = "HEALTHY"
            reasons = []
            print(f"\n  🟢 Model is healthy — no retraining needed.")

        monitoring_results.append({
            "model_name": model_name,
            "status": overall_status,
            "feature_drift": feature_drift,
            "prediction_drift": prediction_drift,
            "performance": performance,
            "needs_retraining": needs_retraining,
            "reasons": reasons,
            "checked_at": datetime.now().isoformat(),
        })

    except Exception as e:
        print(f"  ❌ Monitoring failed for {model_name}: {e}")
        monitoring_results.append({
            "model_name": model_name,
            "status": "ERROR",
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        })

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Generate Model Health Report

# COMMAND ----------

print("\n" + "=" * 70)
print("  MODEL HEALTH REPORT")
print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)

for result in monitoring_results:
    status_icon = {
        "HEALTHY": "🟢",
        "RETRAIN_RECOMMENDED": "🔴",
        "ERROR": "⚠",
    }.get(result["status"], "❓")

    print(f"\n  {status_icon} {result['model_name']}: {result['status']}")
    if result.get("reasons"):
        for r in result["reasons"]:
            print(f"     → {r}")
    if result.get("error"):
        print(f"     Error: {result['error']}")

# Write report to gold lakehouse
report_rows = []
for result in monitoring_results:
    report_rows.append({
        "model_name": result["model_name"],
        "status": result["status"],
        "needs_retraining": result.get("needs_retraining", False),
        "feature_drift_count": len([
            d for d in result.get("feature_drift", {}).values()
            if d.get("drift_level") == "Significant"
        ]),
        "prediction_drift_psi": result.get("prediction_drift", {}).get("psi", 0.0),
        "performance_metric": result.get("performance", {}).get("metric_value", 0.0),
        "performance_threshold": result.get("performance", {}).get("threshold", 0.0),
        "reasons": "; ".join(result.get("reasons", [])),
        "checked_at": result["checked_at"],
    })

df_report = spark.createDataFrame(pd.DataFrame(report_rows))
df_report = df_report.withColumn("_created_at", current_timestamp())

(
    df_report
    .write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable("ml_model_health_report")
)

print(f"\n✅ Model health report appended to ml_model_health_report")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Trigger Retraining if Drift Exceeds Thresholds

# COMMAND ----------

retrain_models = [
    r["model_name"] for r in monitoring_results
    if r.get("needs_retraining", False)
]

if retrain_models:
    print(f"🔄 Models requiring retraining: {', '.join(retrain_models)}")
    print()

    # Map model names to their training notebook paths
    RETRAIN_NOTEBOOK_MAP = {
        "demand-forecaster": "/notebooks/data-science/demand_forecasting",
        "churn-predictor": "/notebooks/data-science/churn_prediction",
    }

    for model_name in retrain_models:
        notebook_path = RETRAIN_NOTEBOOK_MAP.get(model_name)
        if notebook_path:
            print(f"  ► Triggering retraining for {model_name}...")
            print(f"    Notebook: {notebook_path}")

            # In Fabric, use mssparkutils to trigger notebook execution:
            # mssparkutils.notebook.run(notebook_path, timeout_seconds=3600)
            #
            # For this monitoring notebook, we log the intent and let the
            # orchestrating data pipeline handle the actual execution.
            print(f"    ℹ Retraining logged. Execute via data pipeline or manual run.")
        else:
            print(f"  ⚠ No training notebook mapped for {model_name}")
else:
    print("✅ No models require retraining at this time.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Log Monitoring Metrics to MLflow

# COMMAND ----------

mlflow.set_experiment(MONITORING_EXPERIMENT)

with mlflow.start_run(run_name=f"monitoring-{datetime.now().strftime('%Y%m%d-%H%M')}"):
    mlflow.log_param("monitoring_date", datetime.now().isoformat())
    mlflow.log_param("models_monitored", ", ".join(MODELS_TO_MONITOR.keys()))
    mlflow.log_metric("models_healthy", sum(1 for r in monitoring_results if r["status"] == "HEALTHY"))
    mlflow.log_metric("models_retrain_needed", len(retrain_models))
    mlflow.log_metric("models_errored", sum(1 for r in monitoring_results if r["status"] == "ERROR"))

    for result in monitoring_results:
        name = result["model_name"].replace("-", "_")
        mlflow.log_metric(f"{name}_pred_drift_psi", result.get("prediction_drift", {}).get("psi", 0.0))
        perf = result.get("performance", {}).get("metric_value", 0.0)
        mlflow.log_metric(f"{name}_performance", perf)

    print("✅ Monitoring metrics logged to MLflow.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Summary
# MAGIC
# MAGIC | Item | Value |
# MAGIC |---|---|
# MAGIC | Models monitored | demand-forecaster, churn-predictor |
# MAGIC | Drift method | PSI (features) + KS test (predictions) |
# MAGIC | PSI threshold | 0.20 (significant drift) |
# MAGIC | Performance thresholds | MAPE < 0.25 (demand), AUC > 0.70 (churn) |
# MAGIC | Output table | `ml_model_health_report` (append-only) |
# MAGIC | MLflow experiment | `tt-model-monitoring` |
# MAGIC | Schedule | Daily, after batch scoring completes |

print("Model monitoring notebook complete.")
