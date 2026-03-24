"""
Generate IoT sensor telemetry data for Contoso Global Retail stores.

Produces time-series readings at ~5-minute intervals for the last 30 days
of the configured date range.  Data is written as chunked Parquet part
files for GB-scale output (100 M+ rows).

Strategy
--------
Instead of iterating store-by-store and sensor-by-sensor, each chunk
independently draws random (store, sensor, timestamp) triples, generates
values from the matching sensor profile, and writes a part file.  Per-chunk
RNG seeding (``cfg.SEED + chunk_idx``) guarantees reproducibility regardless
of execution order.

Output: <output_dir>/iot_telemetry/part_XXXXXXXXXX.parquet
"""

import os

import numpy as np
import pandas as pd
from tqdm import tqdm

import config as cfg

# ---------------------------------------------------------------------------
# Sensor baselines: (mean_value, std_dev, unit)
# ---------------------------------------------------------------------------
SENSOR_PROFILES = {
    "Temperature": (21.0, 3.0, "°C"),
    "Humidity": (45.0, 10.0, "%"),
    "Foot Traffic": (120.0, 60.0, "people/hr"),
    "Energy": (350.0, 80.0, "kWh"),
    "Door Counter": (200.0, 80.0, "events"),
}

# Pre-compute lookup arrays aligned with cfg.SENSOR_TYPES
_SENSOR_MEANS = np.array([SENSOR_PROFILES[s][0] for s in cfg.SENSOR_TYPES])
_SENSOR_STDS = np.array([SENSOR_PROFILES[s][1] for s in cfg.SENSOR_TYPES])
_SENSOR_UNITS = np.array([SENSOR_PROFILES[s][2] for s in cfg.SENSOR_TYPES])

# Indices of sensors whose values must be non-negative integers
_INTEGER_SENSOR_INDICES = np.array(
    [i for i, s in enumerate(cfg.SENSOR_TYPES)
     if s in ("Foot Traffic", "Door Counter")]
)


# ---------------------------------------------------------------------------
# Vectorized helpers
# ---------------------------------------------------------------------------

def _vectorized_status(sensor_types: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Vectorized status assignment matching original threshold logic.

    Order: set Warning first, then Critical (Critical is a strict subset
    of Warning ranges, so it correctly overwrites).
    """
    status = np.full(len(values), "Normal", dtype=object)

    # --- Temperature ---
    temp_mask = sensor_types == "Temperature"
    if temp_mask.any():
        status[temp_mask & ((values < 15) | (values > 30))] = "Warning"
        status[temp_mask & ((values < 10) | (values > 35))] = "Critical"

    # --- Humidity ---
    hum_mask = sensor_types == "Humidity"
    if hum_mask.any():
        status[hum_mask & ((values < 25) | (values > 70))] = "Warning"
        status[hum_mask & ((values < 15) | (values > 85))] = "Critical"

    # --- Energy ---
    eng_mask = sensor_types == "Energy"
    if eng_mask.any():
        status[eng_mask & (values > 500)] = "Warning"
        status[eng_mask & (values > 600)] = "Critical"

    return status


def _build_device_id_table(num_stores: int) -> np.ndarray:
    """Pre-compute a (num_stores, num_sensors) table of device-ID strings."""
    n_sensors = len(cfg.SENSOR_TYPES)
    table = np.empty((num_stores, n_sensors), dtype=object)
    for si in range(num_stores):
        store = f"S-{si + 1:04d}"
        for ti, stype in enumerate(cfg.SENSOR_TYPES):
            table[si, ti] = f"IOT-{store}-{stype[:4].upper()}-{ti + 1}"
    return table


def _build_store_id_array(num_stores: int) -> np.ndarray:
    """Pre-compute array of store-ID strings."""
    return np.array([f"S-{n:04d}" for n in range(1, num_stores + 1)])


# ---------------------------------------------------------------------------
# Chunk generator
# ---------------------------------------------------------------------------

def _generate_chunk(
    chunk_idx: int,
    chunk_size: int,
    timestamps: np.ndarray,
    sensor_type_arr: np.ndarray,
    device_id_table: np.ndarray,
    store_id_arr: np.ndarray,
    num_stores: int,
) -> pd.DataFrame:
    """Generate one chunk of IoT readings — fully vectorized, no row loops."""
    rng = np.random.default_rng(cfg.SEED + chunk_idx)

    # ---- random assignments ------------------------------------------------
    store_indices = rng.integers(0, num_stores, size=chunk_size)
    sensor_indices = rng.integers(0, len(cfg.SENSOR_TYPES), size=chunk_size)
    ts_indices = rng.integers(0, len(timestamps), size=chunk_size)

    # ---- look up pre-computed arrays via fancy indexing ---------------------
    store_ids = store_id_arr[store_indices]
    sensor_types = sensor_type_arr[sensor_indices]
    device_ids = device_id_table[store_indices, sensor_indices]
    ts = timestamps[ts_indices]
    units = _SENSOR_UNITS[sensor_indices]

    # ---- generate values from per-sensor-type distributions ----------------
    means = _SENSOR_MEANS[sensor_indices]
    stds = _SENSOR_STDS[sensor_indices]
    values = rng.normal(means, stds)

    # Integer-valued sensors: clip ≥ 0 and truncate to whole numbers
    for idx in _INTEGER_SENSOR_INDICES:
        mask = sensor_indices == idx
        values[mask] = np.clip(values[mask], 0, None).astype(np.int64).astype(np.float64)

    values = np.round(values, 2)

    # ---- vectorized status -------------------------------------------------
    status = _vectorized_status(sensor_types, values)

    # ---- UUID-like reading IDs (batch hex slicing) -------------------------
    raw_hex = rng.bytes(16 * chunk_size).hex()
    reading_ids = [
        (
            f"{raw_hex[i:i+8]}-{raw_hex[i+8:i+12]}-"
            f"{raw_hex[i+12:i+16]}-{raw_hex[i+16:i+20]}-"
            f"{raw_hex[i+20:i+32]}"
        )
        for i in range(0, 32 * chunk_size, 32)
    ]

    return pd.DataFrame(
        {
            "reading_id": reading_ids,
            "device_id": device_ids,
            "store_id": store_ids,
            "sensor_type": sensor_types,
            "timestamp": ts,
            "value": values,
            "unit": units,
            "status": status,
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Write IoT telemetry as chunked Parquet part files."""
    out_dir = os.path.join(cfg.OUTPUT_DIR, "iot_telemetry")
    os.makedirs(out_dir, exist_ok=True)

    total = cfg.NUM_IOT_READINGS
    chunk_size = cfg.CHUNK_SIZE
    n_chunks = -(-total // chunk_size)  # ceiling division

    # Shared pre-computed arrays (built once, reused every chunk)
    iot_start = pd.Timestamp(cfg.END_DATE) - pd.Timedelta(days=cfg.IOT_DAYS)
    timestamps = pd.date_range(
        iot_start, pd.Timestamp(cfg.END_DATE), freq="5min"
    ).values

    sensor_type_arr = np.array(cfg.SENSOR_TYPES)
    num_stores = cfg.NUM_STORES
    device_id_table = _build_device_id_table(num_stores)
    store_id_arr = _build_store_id_array(num_stores)

    print(f"Generating IoT telemetry … {total:,} readings in {n_chunks} chunks")
    rows_written = 0

    for chunk_idx in tqdm(range(n_chunks), desc="iot_telemetry", unit="chunk"):
        remaining = total - rows_written
        cur_size = min(chunk_size, remaining)

        df = _generate_chunk(
            chunk_idx=chunk_idx,
            chunk_size=cur_size,
            timestamps=timestamps,
            sensor_type_arr=sensor_type_arr,
            device_id_table=device_id_table,
            store_id_arr=store_id_arr,
            num_stores=num_stores,
        )

        part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
        df.to_parquet(part_path, index=False, engine="pyarrow", compression="snappy")
        rows_written += len(df)

    print(f"  ✓ {rows_written:,} readings → {out_dir}/")


if __name__ == "__main__":
    main()
