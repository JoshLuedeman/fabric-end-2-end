"""
Generate customer dimension data for Contoso Global Retail.

Output: customers.parquet
"""

import os
import sys

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

# ---------------------------------------------------------------------------
# Locale-aware Faker instances
# ---------------------------------------------------------------------------
LOCALE_MAP = {
    "US": "en_US",
    "UK": "en_GB",
    "DE": "de_DE",
    "JP": "ja_JP",
    "AU": "en_AU",
}


def _make_faker(locale: str, seed: int) -> Faker:
    f = Faker(locale)
    f.seed_instance(seed)
    return f


def generate_customers() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    fakers = {cc: _make_faker(loc, cfg.SEED) for cc, loc in LOCALE_MAP.items()}

    countries = list(cfg.COUNTRIES.keys())
    weights = list(cfg.COUNTRIES.values())
    country_assignments = rng.choice(countries, size=cfg.NUM_CUSTOMERS, p=weights)

    rows: list[dict] = []
    for i in range(1, cfg.NUM_CUSTOMERS + 1):
        cc = country_assignments[i - 1]
        fake = fakers[cc]

        first = fake.first_name()
        last = fake.last_name()
        email = f"{first.lower()}.{last.lower()}{i}@{fake.free_email_domain()}"

        loyalty = rng.choice(cfg.LOYALTY_TIERS, p=cfg.LOYALTY_WEIGHTS)
        segment = rng.choice(cfg.CUSTOMER_SEGMENTS, p=cfg.SEGMENT_WEIGHTS)

        # Lifetime value correlates loosely with segment
        ltv_base = {"Budget": 100, "Value": 500, "Premium": 2000, "Luxury": 8000}
        ltv = round(float(rng.exponential(ltv_base[segment])), 2)

        reg_date = cfg.START_DATE + pd.Timedelta(
            days=int(rng.integers(0, (cfg.END_DATE - cfg.START_DATE).days))
        )

        rows.append(
            {
                "customer_id": cfg.customer_id(i),
                "first_name": first,
                "last_name": last,
                "email": email,
                "phone": fake.phone_number(),
                "address": fake.street_address(),
                "city": fake.city(),
                "state": fake.state() if cc in ("US", "AU") else fake.city(),
                "country": cc,
                "postal_code": fake.postcode(),
                "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80),
                "registration_date": reg_date,
                "loyalty_tier": loyalty,
                "customer_segment": segment,
                "lifetime_value": ltv,
                "is_active": bool(rng.random() < 0.90),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating customers …")
    df = generate_customers()
    path = os.path.join(cfg.OUTPUT_DIR, "customers.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} customers → {path}")


if __name__ == "__main__":
    main()
