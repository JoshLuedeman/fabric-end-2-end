"""Generate promotion dimension and promotion-results fact data for Contoso Global Retail.

Outputs
-------
- output/promotions.parquet                        (single file, snappy-compressed)
- output/promotion_results/part_XXXXXXXXXX.parquet  (chunked, snappy-compressed)

``promotions`` is a small dimension table (default 5 000 rows) built as a
single DataFrame.  ``promotion_results`` is a large fact table (default 20 M
rows) written in chunks of ``cfg.CHUNK_SIZE`` so peak memory stays bounded.
Both generators are fully vectorised with NumPy.
"""

from __future__ import annotations

import os
import uuid

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import config as cfg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMO_TYPES = [
    "percentage_off",
    "bogo",
    "bundle",
    "loyalty_multiplier",
    "flash_sale",
    "seasonal",
]
PROMO_TYPE_WEIGHTS = [0.35, 0.15, 0.10, 0.10, 0.15, 0.15]

CHANNELS = ["all", "online", "in_store"]
CHANNEL_WEIGHTS = [0.50, 0.30, 0.20]

_NAME_SEASONS = ["Summer", "Winter", "Spring", "Fall", "Holiday", "Back-to-School"]
_NAME_EVENTS = [
    "Sale",
    "Blowout",
    "Clearance",
    "Flash Deal",
    "Mega Deal",
    "Savings Event",
]
_NAME_YEARS = ["2022", "2023", "2024", "2025"]

# Discount ranges keyed by promo type  (min_pct, max_pct)
_DISCOUNT_RANGES: dict[str, tuple[float, float]] = {
    "percentage_off": (0.05, 0.40),
    "bogo": (0.40, 0.50),
    "bundle": (0.10, 0.30),
    "loyalty_multiplier": (0.05, 0.20),
    "flash_sale": (0.15, 0.50),
    "seasonal": (0.10, 0.35),
}

# Duration ranges keyed by promo type  (min_days, max_days)
_DURATION_RANGES: dict[str, tuple[int, int]] = {
    "percentage_off": (7, 28),
    "bogo": (7, 28),
    "bundle": (7, 28),
    "loyalty_multiplier": (7, 28),
    "flash_sale": (7, 28),
    "seasonal": (14, 56),
}

CHUNK_SIZE = cfg.CHUNK_SIZE

# Arrow schema for promotion_results part files.
_RESULTS_SCHEMA = pa.schema(
    [
        pa.field("result_id", pa.string()),
        pa.field("promo_id", pa.string()),
        pa.field("transaction_id", pa.string()),
        pa.field("customer_id", pa.string()),
        pa.field("redemption_date", pa.timestamp("us")),
        pa.field("discount_amount", pa.float64()),
        pa.field("attributed_revenue", pa.float64()),
    ]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vectorised_uuids(rng: np.random.Generator, n: int) -> list[str]:
    """Return *n* UUID-v4-style strings seeded from *rng*."""
    raw = rng.bytes(16 * n)
    return [str(uuid.UUID(bytes=raw[i * 16 : (i + 1) * 16])) for i in range(n)]


# ---------------------------------------------------------------------------
# Promotions (dimension)
# ---------------------------------------------------------------------------

def generate_promotions() -> pd.DataFrame:
    """Return a DataFrame of *cfg.NUM_PROMOTIONS* promotion rows (vectorised)."""
    n = cfg.NUM_PROMOTIONS
    rng = np.random.default_rng(cfg.SEED)
    total_days = (cfg.END_DATE - cfg.START_DATE).days

    # --- promo_id ---
    ids = np.arange(1, n + 1)
    promo_ids = np.array([cfg.promo_id(i) for i in ids])

    # --- type ---
    types = rng.choice(PROMO_TYPES, size=n, p=PROMO_TYPE_WEIGHTS)

    # --- name  (e.g. "Summer Sale 2023", "Black Friday 2024", ...) ---
    categories = list(cfg.PRODUCT_CATEGORIES.keys())
    seasons = rng.choice(_NAME_SEASONS, size=n)
    events = rng.choice(_NAME_EVENTS, size=n)
    years = rng.choice(_NAME_YEARS, size=n)
    # ~40 % get a category tag, ~30 % get a discount hint, rest plain
    roll = rng.random(size=n)
    cat_picks = np.array(categories, dtype=object)[
        rng.integers(0, len(categories), size=n)
    ]
    discount_hints = np.array(
        [f"{int(d)}% Off" for d in rng.integers(5, 51, size=n)]
    )
    names = np.where(
        roll < 0.40,
        np.char.add(
            np.char.add(seasons.astype(str), " "),
            np.char.add(cat_picks.astype(str), np.char.add(" ", discount_hints)),
        ),
        np.where(
            roll < 0.70,
            np.char.add(
                np.char.add(seasons.astype(str), " "),
                np.char.add(events.astype(str), np.char.add(" ", years.astype(str))),
            ),
            np.char.add(
                np.char.add(events.astype(str), " "),
                years.astype(str),
            ),
        ),
    )

    # --- category_targeted  (~30 % null = targets all categories) ---
    cat_targeted = np.array(categories, dtype=object)[
        rng.integers(0, len(categories), size=n)
    ]
    null_mask = rng.random(size=n) < 0.30
    cat_targeted = np.where(null_mask, None, cat_targeted)

    # --- start_date / end_date ---
    start_offsets = rng.integers(0, total_days, size=n)
    base_date = np.datetime64(cfg.START_DATE, "D")
    start_dates = base_date + start_offsets.astype("timedelta64[D]")

    # Duration depends on type
    durations = np.empty(n, dtype=np.int64)
    for ptype in PROMO_TYPES:
        mask = types == ptype
        lo, hi = _DURATION_RANGES[ptype]
        durations[mask] = rng.integers(lo, hi + 1, size=int(mask.sum()))
    end_dates = start_dates + durations.astype("timedelta64[D]")

    # --- discount_pct  (varies by type) ---
    discount_pct = np.empty(n, dtype=np.float64)
    for ptype in PROMO_TYPES:
        mask = types == ptype
        lo, hi = _DISCOUNT_RANGES[ptype]
        discount_pct[mask] = rng.uniform(lo, hi, size=int(mask.sum()))
    discount_pct = np.round(discount_pct, 4)

    # --- min_purchase, budget, channel ---
    min_purchase = np.round(rng.uniform(0.0, 100.0, size=n), 2)
    budget = np.round(rng.uniform(10_000.0, 500_000.0, size=n), 2)
    channel = rng.choice(CHANNELS, size=n, p=CHANNEL_WEIGHTS)

    return pd.DataFrame(
        {
            "promo_id": promo_ids,
            "name": names,
            "type": types,
            "category_targeted": pd.array(cat_targeted, dtype=pd.StringDtype()),
            "start_date": pd.to_datetime(start_dates),
            "end_date": pd.to_datetime(end_dates),
            "discount_pct": discount_pct,
            "min_purchase": min_purchase,
            "budget": budget,
            "channel": channel,
        }
    )


# ---------------------------------------------------------------------------
# Promotion Results (fact — chunked)
# ---------------------------------------------------------------------------

def _generate_results_chunk(chunk_idx: int, chunk_size: int) -> pa.Table:
    """Build one chunk of promotion_results as a PyArrow Table (vectorised)."""
    rng = np.random.default_rng(cfg.SEED + chunk_idx)
    total_days = (cfg.END_DATE - cfg.START_DATE).days

    # --- result_id (UUID) ---
    result_ids = _vectorised_uuids(rng, chunk_size)

    # --- promo_id (FK) ---
    promo_nums = rng.integers(1, cfg.NUM_PROMOTIONS + 1, size=chunk_size)
    promo_ids = np.array([cfg.promo_id(int(p)) for p in promo_nums])

    # --- transaction_id (UUID — synthetic FK to sales) ---
    transaction_ids = _vectorised_uuids(rng, chunk_size)

    # --- customer_id (FK) ---
    cust_nums = rng.integers(1, cfg.NUM_CUSTOMERS + 1, size=chunk_size)
    customer_ids = np.array([cfg.customer_id(int(c)) for c in cust_nums])

    # --- redemption_date  (random datetime within date range) ---
    day_offsets = rng.integers(0, total_days + 1, size=chunk_size)
    base_ts = np.datetime64(cfg.START_DATE, "us")
    day_deltas = day_offsets.astype("timedelta64[D]").astype("timedelta64[us]")
    # Add a random intra-day offset (0 – 86 399 seconds)
    second_offsets = rng.integers(0, 86_400, size=chunk_size)
    sec_deltas = second_offsets.astype("timedelta64[s]").astype("timedelta64[us]")
    redemption_dates = base_ts + day_deltas + sec_deltas

    # --- discount_amount  (1.00 – 200.00) ---
    discount_amount = np.round(rng.uniform(1.0, 200.0, size=chunk_size), 2)

    # --- attributed_revenue  (10.00 – 2000.00) ---
    attributed_revenue = np.round(rng.uniform(10.0, 2000.0, size=chunk_size), 2)

    return pa.table(
        {
            "result_id": result_ids,
            "promo_id": promo_ids,
            "transaction_id": transaction_ids,
            "customer_id": customer_ids,
            "redemption_date": redemption_dates,
            "discount_amount": discount_amount,
            "attributed_revenue": attributed_revenue,
        },
        schema=_RESULTS_SCHEMA,
    )


def generate_promotion_results(output_dir: str) -> None:
    """Write promotion_results fact table as chunked parquet files.

    Each chunk is ``cfg.CHUNK_SIZE`` rows (last chunk may be smaller).
    Files are written to *output_dir*/promotion_results/part_XXXXXXXXXX.parquet.
    """
    total = cfg.NUM_PROMOTION_RESULTS
    chunk_size = CHUNK_SIZE
    num_chunks = (total + chunk_size - 1) // chunk_size

    out_dir = os.path.join(output_dir, "promotion_results")
    os.makedirs(out_dir, exist_ok=True)

    print(
        f"Generating {total:,} promotion results "
        f"({num_chunks} chunks × {chunk_size:,}) → {out_dir}"
    )

    rows_written = 0
    for chunk_idx in tqdm(range(num_chunks), desc="promotion_results", unit="chunk"):
        remaining = total - rows_written
        current_size = min(chunk_size, remaining)

        table = _generate_results_chunk(chunk_idx, current_size)

        part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
        pq.write_table(table, part_path, compression="snappy")

        rows_written += current_size

    print(
        f"  ✓ {rows_written:,} promotion results → {out_dir}/ "
        f"({num_chunks} part files)"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    output_dir = cfg.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # 1. Promotions (dimension — single file)
    print("Generating promotions …")
    df = generate_promotions()
    promo_path = os.path.join(output_dir, "promotions.parquet")
    df.to_parquet(promo_path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {len(df):,} promotions → {promo_path}")

    # 2. Promotion results (fact — chunked)
    generate_promotion_results(output_dir)


if __name__ == "__main__":
    main()
