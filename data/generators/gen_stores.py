"""
Generate store dimension data for Contoso Global Retail.

Output: stores.parquet
"""

import os

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

# Approximate lat/lon centres per country for realistic coordinates
_GEO_CENTRES = {
    "US": (39.8, -98.5, 10, 25),
    "UK": (53.0, -1.5, 3, 3),
    "DE": (51.0, 10.0, 3, 4),
    "JP": (36.2, 138.3, 4, 4),
    "AU": (-25.3, 133.8, 10, 15),
}

LOCALE_MAP = {
    "US": "en_US",
    "UK": "en_GB",
    "DE": "de_DE",
    "JP": "ja_JP",
    "AU": "en_AU",
}


def generate_stores() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    fakers = {cc: Faker(loc) for cc, loc in LOCALE_MAP.items()}
    for f in fakers.values():
        f.seed_instance(cfg.SEED)

    countries = list(cfg.COUNTRIES.keys())
    weights = list(cfg.COUNTRIES.values())
    country_assignments = rng.choice(countries, size=cfg.NUM_STORES, p=weights)

    # Assign regions based on country
    def _region(cc: str, idx: int) -> str:
        if cc in ("UK", "DE", "JP", "AU"):
            return "International"
        quadrant = idx % 4
        return ["North", "South", "East", "West"][quadrant]

    rows: list[dict] = []
    for i in range(1, cfg.NUM_STORES + 1):
        cc = country_assignments[i - 1]
        fake = fakers[cc]

        store_type = rng.choice(cfg.STORE_TYPES, p=cfg.STORE_TYPE_WEIGHTS)

        # Lat/lon with jitter
        lat_c, lon_c, lat_spread, lon_spread = _GEO_CENTRES[cc]
        lat = round(lat_c + float(rng.normal(0, lat_spread)), 6)
        lon = round(lon_c + float(rng.normal(0, lon_spread)), 6)

        sqft = int(rng.integers(1_000, 80_000)) if store_type != "Online" else 0
        opening_date = cfg.START_DATE - pd.Timedelta(
            days=int(rng.integers(0, 3650))  # up to 10 years before start
        )

        city = fake.city()
        store_name = f"Contoso {city} {store_type}"

        rows.append(
            {
                "store_id": cfg.store_id(i),
                "store_name": store_name,
                "store_type": store_type,
                "address": fake.street_address(),
                "city": city,
                "state": fake.state() if cc in ("US", "AU") else fake.city(),
                "country": cc,
                "postal_code": fake.postcode(),
                "latitude": lat,
                "longitude": lon,
                "square_footage": sqft,
                "opening_date": opening_date,
                "manager_name": fake.name(),
                "region": _region(cc, i),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating stores …")
    df = generate_stores()
    path = os.path.join(cfg.OUTPUT_DIR, "stores.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} stores → {path}")


if __name__ == "__main__":
    main()
