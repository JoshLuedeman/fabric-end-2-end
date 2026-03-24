"""
Generate fact sales transaction data for Contoso Global Retail.

Includes seasonal patterns (holiday peak Nov-Dec, summer sports bump)
and weekday/weekend volume variation.

Output: sales_transactions.parquet
"""

import os
import uuid

import numpy as np
import pandas as pd

import config as cfg


def _seasonal_weight(month: int) -> float:
    """Return a relative volume multiplier for the given month."""
    weights = {
        1: 0.80, 2: 0.75, 3: 0.85, 4: 0.90,
        5: 0.95, 6: 1.05, 7: 1.10, 8: 1.05,
        9: 0.90, 10: 0.95, 11: 1.30, 12: 1.50,
    }
    return weights[month]


def _day_of_week_weight(dow: int) -> float:
    """0=Monday … 6=Sunday. Weekends get more traffic."""
    if dow >= 5:  # Sat/Sun
        return 1.30
    if dow == 4:  # Friday
        return 1.10
    return 0.90


def generate_sales_transactions() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)

    # Pre-compute date pool with seasonal + weekday weights
    total_days = (cfg.END_DATE - cfg.START_DATE).days + 1
    dates = pd.date_range(cfg.START_DATE, cfg.END_DATE, freq="D")
    date_weights = np.array(
        [_seasonal_weight(d.month) * _day_of_week_weight(d.dayofweek) for d in dates]
    )
    date_weights /= date_weights.sum()

    # Draw transaction dates
    date_indices = rng.choice(len(dates), size=cfg.NUM_SALES_TRANSACTIONS, p=date_weights)
    txn_dates = dates[date_indices]

    # Random times biased toward business hours (9-21)
    hours = rng.normal(15, 3, size=cfg.NUM_SALES_TRANSACTIONS).clip(0, 23).astype(int)
    minutes = rng.integers(0, 60, size=cfg.NUM_SALES_TRANSACTIONS)
    seconds = rng.integers(0, 60, size=cfg.NUM_SALES_TRANSACTIONS)
    txn_times = pd.array(
        [f"{h:02d}:{m:02d}:{s:02d}" for h, m, s in zip(hours, minutes, seconds)],
        dtype="string",
    )

    customer_ids = [
        cfg.customer_id(int(n))
        for n in rng.integers(1, cfg.NUM_CUSTOMERS + 1, size=cfg.NUM_SALES_TRANSACTIONS)
    ]
    product_ids = [
        cfg.product_id(int(n))
        for n in rng.integers(1, cfg.NUM_PRODUCTS + 1, size=cfg.NUM_SALES_TRANSACTIONS)
    ]
    store_ids = [
        cfg.store_id(int(n))
        for n in rng.integers(1, cfg.NUM_STORES + 1, size=cfg.NUM_SALES_TRANSACTIONS)
    ]

    quantities = rng.integers(1, 11, size=cfg.NUM_SALES_TRANSACTIONS)

    # Unit prices pulled from a reasonable range; actual analysis can join to products
    unit_prices = np.round(rng.uniform(5.0, 500.0, size=cfg.NUM_SALES_TRANSACTIONS), 2)
    discount_pcts = np.round(rng.uniform(0, 0.30, size=cfg.NUM_SALES_TRANSACTIONS), 2)
    totals = np.round(quantities * unit_prices * (1 - discount_pcts), 2)

    payment_methods = rng.choice(
        cfg.PAYMENT_METHODS, size=cfg.NUM_SALES_TRANSACTIONS, p=cfg.PAYMENT_WEIGHTS
    )
    channels = rng.choice(
        cfg.CHANNELS, size=cfg.NUM_SALES_TRANSACTIONS, p=cfg.CHANNEL_WEIGHTS
    )

    transaction_ids = [str(uuid.UUID(bytes=rng.bytes(16))) for _ in range(cfg.NUM_SALES_TRANSACTIONS)]

    df = pd.DataFrame(
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
    return df


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating sales transactions …")
    df = generate_sales_transactions()
    path = os.path.join(cfg.OUTPUT_DIR, "sales_transactions.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} transactions → {path}")


if __name__ == "__main__":
    main()
