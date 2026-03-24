"""
Generate store dimension data for Tales & Timber.

Output: stores.parquet (snappy-compressed)

Vectorised where possible — Faker is only used once per locale to build
city / address / name pools, then NumPy samples from those pools.
"""

import os

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg

# ---------------------------------------------------------------------------
# Approximate lat/lon centres per country  (lat, lon, lat_spread, lon_spread)
# ---------------------------------------------------------------------------
_GEO_CENTRES: dict[str, tuple[float, float, float, float]] = {
    "US": (39.8, -98.5, 10, 25),
    "UK": (53.0, -1.5, 3, 3),
    "DE": (51.0, 10.0, 3, 4),
    "JP": (36.2, 138.3, 4, 4),
    "AU": (-25.3, 133.8, 10, 15),
    "BR": (-14.2, -51.9, 10, 15),
    "IN": (20.6, 78.9, 8, 10),
    "FR": (46.6, 2.2, 3, 4),
}

# ---------------------------------------------------------------------------
# Faker locale per country code
# ---------------------------------------------------------------------------
LOCALE_MAP: dict[str, str] = {
    "US": "en_US",
    "UK": "en_GB",
    "DE": "de_DE",
    "JP": "ja_JP",
    "AU": "en_AU",
    "BR": "pt_BR",
    "IN": "en_IN",
    "FR": "fr_FR",
}

# ---------------------------------------------------------------------------
# Region mapping
# ---------------------------------------------------------------------------
_DIRECTIONAL = np.array(["North", "South", "East", "West"])

_COUNTRY_REGION: dict[str, str] = {
    "UK": "EMEA",
    "DE": "EMEA",
    "FR": "EMEA",
    "JP": "APAC",
    "AU": "APAC",
    "IN": "APAC",
    "BR": "LATAM",
}


def _region(country: np.ndarray, index: np.ndarray) -> np.ndarray:
    """Vectorised region assignment.

    US stores cycle through North / South / East / West based on their
    1-based index.  All other countries map to a fixed macro-region.
    """
    regions = np.where(
        country == "US",
        _DIRECTIONAL[index % 4],
        np.array([_COUNTRY_REGION.get(c, "International") for c in country]),
    )
    return regions


# ---------------------------------------------------------------------------
# Pool size for pre-generated Faker values  (> NUM_STORES to avoid repeats)
# ---------------------------------------------------------------------------
_POOL_SIZE = 800


def _build_pools(
    fakers: dict[str, Faker],
) -> dict[str, dict[str, np.ndarray]]:
    """Pre-generate pools of city, address, state, postcode, and name per locale.

    Returns ``{country_code: {"city": array, "address": array, ...}}``.
    """
    pools: dict[str, dict[str, np.ndarray]] = {}
    for cc, fake in fakers.items():
        cities = np.array([fake.city() for _ in range(_POOL_SIZE)])
        addresses = np.array([fake.street_address() for _ in range(_POOL_SIZE)])
        postcodes = np.array([fake.postcode() for _ in range(_POOL_SIZE)])
        names = np.array([fake.name() for _ in range(_POOL_SIZE)])

        # state() only makes sense for US / AU / BR / IN; others get city()
        if cc in ("US", "AU", "BR", "IN"):
            states = np.array([fake.state() for _ in range(_POOL_SIZE)])
        else:
            states = cities.copy()

        pools[cc] = {
            "city": cities,
            "address": addresses,
            "state": states,
            "postcode": postcodes,
            "name": names,
        }
    return pools


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_stores() -> pd.DataFrame:
    """Create the stores dimension table."""
    n = cfg.NUM_STORES
    rng = np.random.default_rng(cfg.SEED)

    # --- Faker instances & pools -----------------------------------------
    fakers: dict[str, Faker] = {}
    for cc, loc in LOCALE_MAP.items():
        f = Faker(loc)
        f.seed_instance(cfg.SEED)
        fakers[cc] = f

    pools = _build_pools(fakers)

    # --- Country assignments (vectorised) --------------------------------
    countries_list = list(cfg.COUNTRIES.keys())
    weights = np.array(list(cfg.COUNTRIES.values()))
    country = rng.choice(countries_list, size=n, p=weights)

    # --- Store type (vectorised) -----------------------------------------
    store_type = rng.choice(
        cfg.STORE_TYPES, size=n, p=cfg.STORE_TYPE_WEIGHTS,
    )

    # --- 1-based index array ---------------------------------------------
    idx = np.arange(1, n + 1)

    # --- Store IDs (vectorised via list comprehension on ints) -----------
    store_id = np.array([cfg.store_id(i) for i in idx])

    # --- Regions (vectorised) --------------------------------------------
    region = _region(country, idx)

    # --- Geo coordinates (vectorised per country) ------------------------
    lat = np.empty(n)
    lon = np.empty(n)
    for cc, (lat_c, lon_c, lat_sp, lon_sp) in _GEO_CENTRES.items():
        mask = country == cc
        count = int(mask.sum())
        if count == 0:
            continue
        lat[mask] = lat_c + rng.normal(0, lat_sp, size=count)
        lon[mask] = lon_c + rng.normal(0, lon_sp, size=count)
    lat = np.round(lat, 6)
    lon = np.round(lon, 6)

    # --- Square footage (vectorised) -------------------------------------
    sqft = rng.integers(1_000, 80_000, size=n)
    sqft = np.where(store_type == "Online", 0, sqft)

    # --- Opening date (vectorised) ---------------------------------------
    days_back = rng.integers(0, 3650, size=n)
    base = np.datetime64(cfg.START_DATE, "D")
    opening_date = base - days_back.astype("timedelta64[D]")

    # --- Faker-sourced fields: sample from pre-built pools ---------------
    city = np.empty(n, dtype=object)
    address = np.empty(n, dtype=object)
    state = np.empty(n, dtype=object)
    postcode = np.empty(n, dtype=object)
    manager = np.empty(n, dtype=object)

    for cc in pools:
        mask = country == cc
        count = int(mask.sum())
        if count == 0:
            continue
        p = pools[cc]
        pick = lambda arr: arr[rng.integers(0, len(arr), size=count)]  # noqa: E731
        city[mask] = pick(p["city"])
        address[mask] = pick(p["address"])
        state[mask] = pick(p["state"])
        postcode[mask] = pick(p["postcode"])
        manager[mask] = pick(p["name"])

    # --- Store name (vectorised string concat) ---------------------------
    store_name = np.char.add(
        np.char.add("Tales & Timber ", city.astype(str)),
        np.char.add(" ", store_type.astype(str)),
    )

    # --- Assemble DataFrame ----------------------------------------------
    df = pd.DataFrame(
        {
            "store_id": store_id,
            "store_name": store_name,
            "store_type": store_type,
            "address": address,
            "city": city,
            "state": state,
            "country": country,
            "postal_code": postcode,
            "latitude": lat,
            "longitude": lon,
            "square_footage": sqft,
            "opening_date": pd.to_datetime(opening_date),
            "manager_name": manager,
            "region": region,
        }
    )
    return df


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating stores …")
    df = generate_stores()
    path = os.path.join(cfg.OUTPUT_DIR, "stores.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {len(df):,} stores → {path}")


if __name__ == "__main__":
    main()
