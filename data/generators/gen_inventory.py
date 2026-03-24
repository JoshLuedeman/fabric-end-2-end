"""
Generate inventory movement data for Tales & Timber.

Output: output/inventory/part_XXXXXXXXXX.parquet  (chunked, Snappy-compressed)

Generates ``cfg.NUM_INVENTORY_RECORDS`` rows (default 50 M) in chunks of
``cfg.CHUNK_SIZE`` (default 1 M) so that peak memory stays bounded regardless
of total volume.  Each chunk is fully vectorised with NumPy.
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

# ── Constants ─────────────────────────────────────────────────────────────
MOVEMENT_TYPES = ["Receipt", "Sale", "Transfer", "Adjustment", "Return"]
MOVEMENT_WEIGHTS = [0.25, 0.40, 0.15, 0.10, 0.10]

# Arrow schema – defined once so every part file is identical.
_ARROW_SCHEMA = pa.schema(
    [
        pa.field("inventory_id", pa.string()),
        pa.field("product_id", pa.string()),
        pa.field("store_id", pa.string()),
        pa.field("date", pa.date32()),
        pa.field("movement_type", pa.string()),
        pa.field("quantity", pa.int32()),
        pa.field("unit_cost", pa.float64()),
        pa.field("on_hand_after", pa.int32()),
        pa.field("reorder_point", pa.int32()),
        pa.field("reorder_quantity", pa.int32()),
    ]
)


# ── Helpers ───────────────────────────────────────────────────────────────
def _vectorised_uuids(rng: np.random.Generator, n: int) -> list[str]:
    """Return *n* UUID-v4-style strings seeded from *rng*."""
    raw = rng.bytes(16 * n)
    return [str(uuid.UUID(bytes=raw[i * 16 : (i + 1) * 16])) for i in range(n)]


def _generate_chunk(chunk_idx: int, chunk_size: int) -> pa.Table:
    """Build one chunk as a PyArrow Table (fully vectorised, zero copies)."""
    rng = np.random.default_rng(cfg.SEED + chunk_idx)
    total_days = (cfg.END_DATE - cfg.START_DATE).days

    # ── IDs ───────────────────────────────────────────────────────────
    inventory_ids = _vectorised_uuids(rng, chunk_size)

    product_nums = rng.integers(1, cfg.NUM_PRODUCTS + 1, size=chunk_size)
    product_ids = np.array([f"P-{n:06d}" for n in product_nums])

    store_nums = rng.integers(1, cfg.NUM_STORES + 1, size=chunk_size)
    store_ids = np.array([f"S-{n:04d}" for n in store_nums])

    # ── Dates ─────────────────────────────────────────────────────────
    day_offsets = rng.integers(0, total_days + 1, size=chunk_size)
    base = np.datetime64(cfg.START_DATE, "D")
    dates = base + day_offsets.astype("timedelta64[D]")

    # ── Movement types & quantities (vectorised by mask) ──────────────
    movement_types = rng.choice(MOVEMENT_TYPES, size=chunk_size, p=MOVEMENT_WEIGHTS)

    quantities = np.zeros(chunk_size, dtype=np.int32)
    for mt, lo, hi in [("Receipt", 10, 500), ("Sale", -20, -1), ("Return", 1, 10)]:
        mask = movement_types == mt
        quantities[mask] = rng.integers(lo, hi + 1, size=mask.sum())
    # Transfer: can be positive or negative
    mask_t = movement_types == "Transfer"
    quantities[mask_t] = rng.integers(-50, 51, size=mask_t.sum())
    # Adjustment: small corrections
    mask_a = movement_types == "Adjustment"
    quantities[mask_a] = rng.integers(-20, 21, size=mask_a.sum())

    # ── Remaining numeric columns ─────────────────────────────────────
    unit_costs = np.round(rng.uniform(2.0, 400.0, size=chunk_size), 2)
    on_hand = rng.integers(0, 1000, size=chunk_size).astype(np.int32)
    reorder_points = rng.integers(10, 100, size=chunk_size).astype(np.int32)
    reorder_quantities = rng.integers(50, 500, size=chunk_size).astype(np.int32)

    # ── Assemble Arrow Table directly ─────────────────────────────────
    table = pa.table(
        {
            "inventory_id": inventory_ids,
            "product_id": product_ids,
            "store_id": store_ids,
            "date": dates,
            "movement_type": movement_types,
            "quantity": quantities,
            "unit_cost": unit_costs,
            "on_hand_after": on_hand,
            "reorder_point": reorder_points,
            "reorder_quantity": reorder_quantities,
        },
        schema=_ARROW_SCHEMA,
    )
    return table


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    total = cfg.NUM_INVENTORY_RECORDS
    chunk_size = cfg.CHUNK_SIZE
    num_chunks = (total + chunk_size - 1) // chunk_size  # ceiling division

    out_dir = os.path.join(cfg.OUTPUT_DIR, "inventory")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Generating {total:,} inventory records "
          f"({num_chunks} chunks × {chunk_size:,}) → {out_dir}")

    rows_written = 0
    for chunk_idx in tqdm(range(num_chunks), desc="inventory", unit="chunk"):
        # Last chunk may be smaller
        remaining = total - rows_written
        current_size = min(chunk_size, remaining)

        table = _generate_chunk(chunk_idx, current_size)

        part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
        pq.write_table(table, part_path, compression="snappy")

        rows_written += current_size

    print(f"  ✓ {rows_written:,} inventory records → {out_dir}/ "
          f"({num_chunks} part files)")


if __name__ == "__main__":
    main()
