"""
Generate supply-chain graph data for Contoso Global Retail.

Outputs:
  - suppliers.parquet       (nodes)
  - warehouses.parquet      (nodes)
  - supply_relationships.parquet  (edges: Supplier → Warehouse with Product)
  - shipments.parquet       (edges: Supplier → Warehouse → Store)
"""

import os
import uuid

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

SUPPLIER_COUNTRIES = [
    "China", "India", "Vietnam", "Mexico", "Germany",
    "US", "Japan", "South Korea", "Brazil", "Turkey",
]

WAREHOUSE_CITIES = [
    ("Chicago", "US"), ("Los Angeles", "US"), ("Houston", "US"),
    ("London", "UK"), ("Manchester", "UK"),
    ("Frankfurt", "DE"), ("Hamburg", "DE"),
    ("Tokyo", "JP"), ("Osaka", "JP"),
    ("Sydney", "AU"), ("Melbourne", "AU"),
    ("Shanghai", "China"), ("Mumbai", "India"),
    ("Mexico City", "Mexico"), ("São Paulo", "Brazil"),
]


# ---- Suppliers ----

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


# ---- Warehouses ----

def generate_warehouses() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED + 1)

    rows: list[dict] = []
    for i in range(1, cfg.NUM_WAREHOUSES + 1):
        city, country = WAREHOUSE_CITIES[i % len(WAREHOUSE_CITIES)]
        rows.append(
            {
                "warehouse_id": cfg.warehouse_id(i),
                "warehouse_name": f"Contoso {city} DC",
                "city": city,
                "country": country,
                "capacity_units": int(rng.integers(5_000, 100_000)),
                "utilization_pct": round(float(rng.uniform(0.40, 0.95)), 2),
            }
        )
    return pd.DataFrame(rows)


# ---- Supply Relationships (Supplier → Warehouse for a Product) ----

def generate_supply_relationships() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED + 2)

    # Each product has 1-3 supplier→warehouse paths
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


# ---- Shipments (Supplier → Warehouse → Store) ----

def generate_shipments() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED + 3)

    # ~2-3x the number of stores × some repeat shipments
    n_shipments = cfg.NUM_STORES * 20  # ~3 000
    total_days = (cfg.END_DATE - cfg.START_DATE).days

    rows: list[dict] = []
    for _ in range(n_shipments):
        sup = int(rng.integers(1, cfg.NUM_SUPPLIERS + 1))
        wh = int(rng.integers(1, cfg.NUM_WAREHOUSES + 1))
        st = int(rng.integers(1, cfg.NUM_STORES + 1))

        ship_offset = int(rng.integers(0, total_days))
        ship_date = cfg.START_DATE + pd.Timedelta(days=ship_offset)
        transit = int(rng.integers(1, 30))
        arrival_date = ship_date + pd.Timedelta(days=transit)

        status = rng.choice(cfg.SHIPMENT_STATUSES, p=cfg.SHIPMENT_STATUS_WEIGHTS)
        qty = int(rng.integers(10, 1000))
        cost = round(float(rng.uniform(50, 5000)), 2)

        rows.append(
            {
                "shipment_id": str(uuid.UUID(bytes=rng.bytes(16))),
                "supplier_id": cfg.supplier_id(sup),
                "warehouse_id": cfg.warehouse_id(wh),
                "store_id": cfg.store_id(st),
                "ship_date": ship_date,
                "arrival_date": arrival_date,
                "status": status,
                "quantity": qty,
                "shipping_cost": cost,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    for name, gen_fn in [
        ("suppliers", generate_suppliers),
        ("warehouses", generate_warehouses),
        ("supply_relationships", generate_supply_relationships),
        ("shipments", generate_shipments),
    ]:
        print(f"Generating {name} …")
        df = gen_fn()
        path = os.path.join(cfg.OUTPUT_DIR, f"{name}.parquet")
        df.to_parquet(path, index=False, engine="pyarrow")
        print(f"  ✓ {len(df):,} rows → {path}")


if __name__ == "__main__":
    main()
