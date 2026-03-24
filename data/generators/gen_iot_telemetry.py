"""
Generate IoT sensor telemetry data for Contoso Global Retail stores.

Produces time-series readings at ~5-minute intervals for the last 30 days
of the configured date range.

Output: iot_telemetry.parquet
"""

import os
import math
import uuid

import numpy as np
import pandas as pd

import config as cfg

# Sensor baselines: (mean_value, std_dev, unit)
SENSOR_PROFILES = {
    "Temperature": (21.0, 3.0, "°C"),
    "Humidity": (45.0, 10.0, "%"),
    "Foot Traffic": (120.0, 60.0, "people/hr"),
    "Energy": (350.0, 80.0, "kWh"),
    "Door Counter": (200.0, 80.0, "events"),
}


def _status(sensor_type: str, value: float) -> str:
    """Determine alert status based on thresholds."""
    if sensor_type == "Temperature":
        if value < 10 or value > 35:
            return "Critical"
        if value < 15 or value > 30:
            return "Warning"
    elif sensor_type == "Humidity":
        if value < 15 or value > 85:
            return "Critical"
        if value < 25 or value > 70:
            return "Warning"
    elif sensor_type == "Energy":
        if value > 600:
            return "Critical"
        if value > 500:
            return "Warning"
    return "Normal"


def generate_iot_telemetry() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)

    target = cfg.NUM_IOT_READINGS

    # Each store gets a handful of sensors; we'll pick a subset of stores
    # to keep the total near target
    intervals_per_day = 24 * 60 // 5  # 288 five-minute slots
    total_readings_per_sensor = cfg.IOT_DAYS * intervals_per_day  # 8 640

    sensors_per_store = len(cfg.SENSOR_TYPES)
    readings_per_store = sensors_per_store * total_readings_per_sensor

    # How many stores to include to land near target
    n_stores = max(1, min(cfg.NUM_STORES, math.ceil(target / readings_per_store)))

    store_indices = rng.choice(
        range(1, cfg.NUM_STORES + 1), size=n_stores, replace=False
    )

    iot_start = cfg.END_DATE - pd.Timedelta(days=cfg.IOT_DAYS)
    timestamps = pd.date_range(iot_start, cfg.END_DATE, freq="5min")

    all_rows: list[dict] = []
    for s_idx in store_indices:
        sid = cfg.store_id(int(s_idx))
        for sensor_num, sensor_type in enumerate(cfg.SENSOR_TYPES, start=1):
            device_id = f"IOT-{sid}-{sensor_type[:4].upper()}-{sensor_num}"
            mean, std, unit = SENSOR_PROFILES[sensor_type]

            values = rng.normal(mean, std, size=len(timestamps))
            # Foot Traffic & Door Counter should be non-negative integers
            if sensor_type in ("Foot Traffic", "Door Counter"):
                values = np.clip(values, 0, None).astype(int).astype(float)

            for ts, val in zip(timestamps, values):
                val_rounded = round(float(val), 2)
                all_rows.append(
                    {
                        "reading_id": str(uuid.UUID(bytes=rng.bytes(16))),
                        "device_id": device_id,
                        "store_id": sid,
                        "sensor_type": sensor_type,
                        "timestamp": ts,
                        "value": val_rounded,
                        "unit": unit,
                        "status": _status(sensor_type, val_rounded),
                    }
                )

        # Stop early if we've reached the target
        if len(all_rows) >= target:
            break

    df = pd.DataFrame(all_rows[:target])
    return df


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating IoT telemetry …")
    df = generate_iot_telemetry()
    path = os.path.join(cfg.OUTPUT_DIR, "iot_telemetry.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} readings → {path}")


if __name__ == "__main__":
    main()
