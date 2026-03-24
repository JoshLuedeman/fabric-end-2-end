"""
Generate inventory movement data for Contoso Global Retail.

Output: inventory.parquet
"""

import os
import uuid

import numpy as np
import pandas as pd

import config as cfg

MOVEMENT_TYPES = ["Receipt", "Sale", "Transfer", "Adjustment", "Return"]
MOVEMENT_WEIGHTS = [0.25, 0.40, 0.15, 0.10, 0.10]


def generate_inventory() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    n = cfg.NUM_INVENTORY_RECORDS

    total_days = (cfg.END_DATE - cfg.START_DATE).days
    dates = [
        cfg.START_DATE + pd.Timedelta(days=int(rng.integers(0, total_days + 1)))
        for _ in range(n)
    ]

    product_ids = [
        cfg.product_id(int(x))
        for x in rng.integers(1, cfg.NUM_PRODUCTS + 1, size=n)
    ]
    store_ids = [
        cfg.store_id(int(x))
        for x in rng.integers(1, cfg.NUM_STORES + 1, size=n)
    ]

    movement_types = rng.choice(MOVEMENT_TYPES, size=n, p=MOVEMENT_WEIGHTS)

    # Quantity depends on movement type
    quantities = np.zeros(n, dtype=int)
    for i, mt in enumerate(movement_types):
        if mt == "Receipt":
            quantities[i] = int(rng.integers(10, 500))
        elif mt == "Sale":
            quantities[i] = -int(rng.integers(1, 20))
        elif mt == "Transfer":
            quantities[i] = int(rng.integers(-50, 51))  # can be in or out
        elif mt == "Adjustment":
            quantities[i] = int(rng.integers(-20, 21))
        elif mt == "Return":
            quantities[i] = int(rng.integers(1, 10))

    unit_costs = np.round(rng.uniform(2.0, 400.0, size=n), 2)
    on_hand = rng.integers(0, 1000, size=n)
    reorder_points = rng.integers(10, 100, size=n)
    reorder_quantities = rng.integers(50, 500, size=n)

    inventory_ids = [str(uuid.UUID(bytes=rng.bytes(16))) for _ in range(n)]

    df = pd.DataFrame(
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
        }
    )
    return df


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating inventory …")
    df = generate_inventory()
    path = os.path.join(cfg.OUTPUT_DIR, "inventory.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} inventory records → {path}")


if __name__ == "__main__":
    main()
