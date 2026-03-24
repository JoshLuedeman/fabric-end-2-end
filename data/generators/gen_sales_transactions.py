"""
Generate fact sales transaction data for Tales & Timber.

Chunked generation for GB-scale output — 200 M rows written as 1 M-row
Parquet part files with Snappy compression.  Each chunk is fully
vectorised via NumPy; no per-row Python loops.

Includes seasonal patterns (holiday peak Nov-Dec, summer sports bump)
and weekday/weekend volume variation.

Output: sales_transactions/part_XXXXXXXXXX.parquet
"""

import math
import os
import uuid

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import config as cfg

# ---------------------------------------------------------------------------
# Seasonal & day-of-week weight look-ups (unchanged from the original)
# ---------------------------------------------------------------------------

_SEASONAL_WEIGHTS: dict[int, float] = {
    1: 0.80, 2: 0.75, 3: 0.85, 4: 0.90,
    5: 0.95, 6: 1.05, 7: 1.10, 8: 1.05,
    9: 0.90, 10: 0.95, 11: 1.30, 12: 1.50,
}

_DOW_WEIGHTS: dict[int, float] = {
    0: 0.90,   # Monday
    1: 0.90,   # Tuesday
    2: 0.90,   # Wednesday
    3: 0.90,   # Thursday
    4: 1.10,   # Friday
    5: 1.30,   # Saturday
    6: 1.30,   # Sunday
}


# ---------------------------------------------------------------------------
# Pre-compute helpers (called once, before the chunk loop)
# ---------------------------------------------------------------------------

def _build_date_weights() -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Return the full date pool and its normalised sampling weights."""
    dates = pd.date_range(cfg.START_DATE, cfg.END_DATE, freq="D")
    weights = np.array(
        [_SEASONAL_WEIGHTS[d.month] * _DOW_WEIGHTS[d.dayofweek] for d in dates]
    )
    weights /= weights.sum()
    return dates, weights


# ---------------------------------------------------------------------------
# Per-chunk generator
# ---------------------------------------------------------------------------

def _generate_chunk(
    chunk_idx: int,
    chunk_size: int,
    dates: pd.DatetimeIndex,
    date_weights: np.ndarray,
) -> pa.Table:
    """Build one chunk of sales transactions as a PyArrow Table.

    Every column is produced via vectorised NumPy operations.  The RNG
    is seeded per-chunk (``cfg.SEED + chunk_idx``) so results are
    reproducible and chunks can be generated in parallel later.
    """
    rng = np.random.default_rng(cfg.SEED + chunk_idx)

    # -- transaction_id  (UUID v4 from bulk random bytes) -------------------
    raw_bytes = rng.bytes(16 * chunk_size)
    transaction_ids = [
        str(uuid.UUID(bytes=raw_bytes[i * 16 : (i + 1) * 16]))
        for i in range(chunk_size)
    ]

    # -- transaction_date  (weighted draw) ----------------------------------
    date_idx = rng.choice(len(dates), size=chunk_size, p=date_weights)
    txn_dates = dates[date_idx]

    # -- transaction_time  (vectorised string build) ------------------------
    hours = rng.normal(15, 3, size=chunk_size).clip(0, 23).astype(np.int32)
    minutes = rng.integers(0, 60, size=chunk_size, dtype=np.int32)
    seconds = rng.integers(0, 60, size=chunk_size, dtype=np.int32)

    h_str = np.char.zfill(hours.astype(str), 2)
    m_str = np.char.zfill(minutes.astype(str), 2)
    s_str = np.char.zfill(seconds.astype(str), 2)
    txn_times = np.char.add(
        np.char.add(np.char.add(np.char.add(h_str, ":"), m_str), ":"), s_str
    )

    # -- foreign keys  (vectorised ID formatting) ---------------------------
    cust_nums = rng.integers(1, cfg.NUM_CUSTOMERS + 1, size=chunk_size)
    customer_ids = np.char.add("C-", np.char.zfill(cust_nums.astype(str), 7))

    prod_nums = rng.integers(1, cfg.NUM_PRODUCTS + 1, size=chunk_size)
    product_ids = np.char.add("P-", np.char.zfill(prod_nums.astype(str), 6))

    store_nums = rng.integers(1, cfg.NUM_STORES + 1, size=chunk_size)
    store_ids = np.char.add("S-", np.char.zfill(store_nums.astype(str), 4))

    # -- measures -----------------------------------------------------------
    quantities = rng.integers(1, 11, size=chunk_size)
    unit_prices = np.round(rng.uniform(5.0, 500.0, size=chunk_size), 2)
    discount_pcts = np.round(rng.uniform(0.0, 0.30, size=chunk_size), 2)
    totals = np.round(quantities * unit_prices * (1 - discount_pcts), 2)

    # -- categorical columns ------------------------------------------------
    payment_methods = rng.choice(
        cfg.PAYMENT_METHODS, size=chunk_size, p=cfg.PAYMENT_WEIGHTS,
    )
    channels = rng.choice(
        cfg.CHANNELS, size=chunk_size, p=cfg.CHANNEL_WEIGHTS,
    )

    # -- assemble PyArrow Table  (zero-copy where possible) -----------------
    table = pa.table(
        {
            "transaction_id": transaction_ids,
            "transaction_date": txn_dates,
            "transaction_time": txn_times,
            "customer_id": customer_ids,
            "product_id": product_ids,
            "store_id": store_ids,
            "quantity": quantities,
            "unit_price": unit_prices,
            "discount_pct": discount_pcts,
            "total_amount": totals,
            "payment_method": payment_methods,
            "channel": channels,
        }
    )
    return table


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Write sales transactions as chunked Parquet part files."""
    out_dir = os.path.join(cfg.OUTPUT_DIR, "sales_transactions")
    os.makedirs(out_dir, exist_ok=True)

    total = cfg.NUM_SALES_TRANSACTIONS
    chunk_size = cfg.CHUNK_SIZE
    num_chunks = math.ceil(total / chunk_size)

    print(
        f"Generating {total:,} sales transactions "
        f"({num_chunks:,} chunks × {chunk_size:,} rows) …"
    )

    # Pre-compute date weights once for all chunks
    dates, date_weights = _build_date_weights()

    rows_written = 0
    with tqdm(total=total, unit="row", unit_scale=True) as pbar:
        for chunk_idx in range(num_chunks):
            current_chunk = min(chunk_size, total - rows_written)

            table = _generate_chunk(chunk_idx, current_chunk, dates, date_weights)

            part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
            pq.write_table(table, part_path, compression="snappy")

            rows_written += current_chunk
            pbar.update(current_chunk)

    print(f"  ✓ {rows_written:,} transactions → {out_dir}/")


if __name__ == "__main__":
    main()
