"""
Generate supply-chain graph data for Tales & Timber  (GB-scale).

Dimension tables (small, single-DataFrame):
  - suppliers.parquet
  - warehouses.parquet
  - supply_relationships.parquet

Fact table (large, chunked writes):
  - shipments/part_NNNNNNNNNN.parquet   (partitioned parquet)
"""

from __future__ import annotations

import math
import os
import uuid

import numpy as np
import pandas as pd
from faker import Faker
from tqdm import tqdm

import config as cfg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPLIER_COUNTRIES = [
    "China", "India", "Vietnam", "Mexico", "Germany",
    "US", "Japan", "South Korea", "Brazil", "Turkey",
]

WAREHOUSE_CITIES = [
    # North America
    ("Chicago", "US"), ("Los Angeles", "US"), ("Houston", "US"),
    # Europe
    ("London", "UK"), ("Manchester", "UK"),
    ("Frankfurt", "DE"), ("Hamburg", "DE"),
    ("Paris", "FR"), ("Lyon", "FR"), ("Marseille", "FR"),
    # Asia-Pacific
    ("Tokyo", "JP"), ("Osaka", "JP"),
    ("Sydney", "AU"), ("Melbourne", "AU"),
    ("Shanghai", "China"),
    ("Mumbai", "IN"), ("Delhi", "IN"), ("Bangalore", "IN"),
    # Latin America
    ("Mexico City", "Mexico"),
    ("São Paulo", "BR"), ("Rio de Janeiro", "BR"),
]

_PARQUET_OPTS: dict = dict(
    index=False,
    engine="pyarrow",
    compression="snappy",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid_batch(rng: np.random.Generator, n: int) -> list[str]:
    """Generate *n* UUID-v4 strings from *rng* in one go."""
    raw = rng.bytes(16 * n)
    return [
        str(uuid.UUID(bytes=raw[i * 16 : (i + 1) * 16]))
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Suppliers  (dimension — small)
# ---------------------------------------------------------------------------

def generate_suppliers() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    fake = Faker()
    Faker.seed(cfg.SEED)

    rows: list[dict] = []
    for i in range(1, cfg.NUM_SUPPLIERS + 1):
        rows.append(
            {
                "supplier_id": cfg.supplier_id(i),
                "supplier_name": f"{fake.company()} Supply Co.",
                "country": rng.choice(SUPPLIER_COUNTRIES),
                "rating": int(rng.integers(1, 6)),
                "lead_time_days": int(rng.integers(3, 90)),
                "is_active": bool(rng.random() < 0.90),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Warehouses  (dimension — small)
# ---------------------------------------------------------------------------

def generate_warehouses() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED + 1)

    rows: list[dict] = []
    for i in range(1, cfg.NUM_WAREHOUSES + 1):
        city, country = WAREHOUSE_CITIES[i % len(WAREHOUSE_CITIES)]
        rows.append(
            {
                "warehouse_id": cfg.warehouse_id(i),
                "warehouse_name": f"Tales & Timber {city} DC",
                "city": city,
                "country": country,
                "capacity_units": int(rng.integers(5_000, 100_000)),
                "utilization_pct": round(float(rng.uniform(0.40, 0.95)), 2),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Supply Relationships  (dimension — small)
# ---------------------------------------------------------------------------

def generate_supply_relationships() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED + 2)

    rows: list[dict] = []
    rel_id = 0
    for p in range(1, cfg.NUM_PRODUCTS + 1):
        n_paths = int(rng.integers(1, 4))
        for _ in range(n_paths):
            rel_id += 1
            sup = int(rng.integers(1, cfg.NUM_SUPPLIERS + 1))
            wh = int(rng.integers(1, cfg.NUM_WAREHOUSES + 1))

            mode = rng.choice(cfg.TRANSPORT_MODES, p=cfg.TRANSPORT_WEIGHTS)
            cost = round(float(rng.uniform(0.5, 25.0)), 2)
            lead = int(rng.integers(2, 60))
            start = cfg.START_DATE + pd.Timedelta(days=int(rng.integers(0, 365)))
            end = start + pd.Timedelta(days=int(rng.integers(365, 1095)))

            rows.append(
                {
                    "relationship_id": rel_id,
                    "supplier_id": cfg.supplier_id(sup),
                    "product_id": cfg.product_id(p),
                    "warehouse_id": cfg.warehouse_id(wh),
                    "transport_mode": mode,
                    "cost_per_unit": cost,
                    "lead_time_days": lead,
                    "contract_start": start,
                    "contract_end": end,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Shipments  (fact — GB-scale, chunked writes)
# ---------------------------------------------------------------------------

# Pre-built lookup arrays so we don't call cfg.*_id() millions of times.
_SUPPLIER_IDS = np.array([cfg.supplier_id(i) for i in range(1, cfg.NUM_SUPPLIERS + 1)])
_WAREHOUSE_IDS = np.array([cfg.warehouse_id(i) for i in range(1, cfg.NUM_WAREHOUSES + 1)])
_STORE_IDS = np.array([cfg.store_id(i) for i in range(1, cfg.NUM_STORES + 1)])
_STATUSES = np.array(cfg.SHIPMENT_STATUSES)
_STATUS_WEIGHTS = np.array(cfg.SHIPMENT_STATUS_WEIGHTS, dtype=np.float64)


def generate_shipments(output_dir: str) -> None:
    """Write shipments as partitioned parquet files into *output_dir*/shipments/.

    Files are named ``part_NNNNNNNNNN.parquet`` (one per chunk).
    Nothing is returned — data is streamed straight to disk.
    """
    shipments_dir = os.path.join(output_dir, "shipments")
    os.makedirs(shipments_dir, exist_ok=True)

    rng = np.random.default_rng(cfg.SEED + 3)
    total_days = (cfg.END_DATE - cfg.START_DATE).days
    origin = pd.Timestamp(cfg.START_DATE)

    n_total = cfg.NUM_SHIPMENTS
    chunk_size = cfg.CHUNK_SIZE
    n_chunks = math.ceil(n_total / chunk_size)
    rows_written = 0

    for chunk_idx in tqdm(range(n_chunks), desc="shipments", unit="chunk"):
        n = min(chunk_size, n_total - rows_written)

        # -- vectorised random draws ----------------------------------------
        sup_idx = rng.integers(0, cfg.NUM_SUPPLIERS, size=n)
        wh_idx = rng.integers(0, cfg.NUM_WAREHOUSES, size=n)
        st_idx = rng.integers(0, cfg.NUM_STORES, size=n)

        ship_offsets = rng.integers(0, total_days, size=n)
        transit_days = rng.integers(1, 30, size=n)

        status_idx = rng.choice(len(_STATUSES), size=n, p=_STATUS_WEIGHTS)
        quantities = rng.integers(10, 1000, size=n)
        costs = np.round(rng.uniform(50.0, 5000.0, size=n), 2)

        # -- build DataFrame in one shot ------------------------------------
        ship_dates = origin + pd.to_timedelta(ship_offsets, unit="D")
        arrival_dates = ship_dates + pd.to_timedelta(transit_days, unit="D")

        df = pd.DataFrame(
            {
                "shipment_id": _uuid_batch(rng, n),
                "supplier_id": _SUPPLIER_IDS[sup_idx],
                "warehouse_id": _WAREHOUSE_IDS[wh_idx],
                "store_id": _STORE_IDS[st_idx],
                "ship_date": ship_dates,
                "arrival_date": arrival_dates,
                "status": _STATUSES[status_idx],
                "quantity": quantities,
                "shipping_cost": costs,
            }
        )

        part_path = os.path.join(
            shipments_dir, f"part_{chunk_idx:010d}.parquet"
        )
        df.to_parquet(part_path, **_PARQUET_OPTS)
        rows_written += n

    print(f"  ✓ {rows_written:,} rows → {shipments_dir}/ ({n_chunks} parts)")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    # -- dimension tables (single DataFrame each) ---------------------------
    for name, gen_fn in [
        ("suppliers", generate_suppliers),
        ("warehouses", generate_warehouses),
        ("supply_relationships", generate_supply_relationships),
    ]:
        print(f"Generating {name} …")
        df = gen_fn()
        path = os.path.join(cfg.OUTPUT_DIR, f"{name}.parquet")
        df.to_parquet(path, **_PARQUET_OPTS)
        print(f"  ✓ {len(df):,} rows → {path}")

    # -- fact table (chunked, writes directly to disk) ----------------------
    print(f"Generating shipments ({cfg.NUM_SHIPMENTS:,} rows, "
          f"chunk_size={cfg.CHUNK_SIZE:,}) …")
    generate_shipments(cfg.OUTPUT_DIR)


if __name__ == "__main__":
    main()
