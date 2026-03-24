"""
Generate customer dimension data for Contoso Global Retail.

Output: customers.parquet

Strategy
--------
At 2 M rows Faker-per-row is prohibitively slow.  Instead we:

1. Build per-locale **pools** (~10 K names / addresses each) with Faker.
2. Sample from those pools with **numpy** (vectorised, fast).
3. Construct every column as a contiguous numpy / pandas array —
   no Python-level row loop touches the hot path.
"""

import os

import numpy as np
import pandas as pd
from faker import Faker
from tqdm import tqdm

import config as cfg

# ---------------------------------------------------------------------------
# Locale-aware Faker instances
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

# Countries whose Faker locale supports a real ``state()`` provider.
_HAS_STATE = frozenset({"US", "AU", "BR", "IN"})

# How many unique values to pre-generate per locale (sampled with replacement).
_POOL_SIZE = 10_000


def _make_faker(locale: str, seed: int) -> Faker:
    f = Faker(locale)
    f.seed_instance(seed)
    return f


# ---------------------------------------------------------------------------
# Pool builder — the *only* place that calls Faker in a loop
# ---------------------------------------------------------------------------

def _build_pools(
    fakers: dict[str, Faker],
) -> dict[str, dict[str, np.ndarray]]:
    """Pre-generate per-locale pools of names, addresses, etc.

    Each value list is converted to a numpy object array so downstream
    sampling is a single fancy-index operation.
    """
    pools: dict[str, dict[str, np.ndarray]] = {}
    for cc, fake in tqdm(fakers.items(), desc="Building locale pools"):
        has_state = cc in _HAS_STATE
        pools[cc] = {
            "first_name": np.array(
                [fake.first_name() for _ in range(_POOL_SIZE)]
            ),
            "last_name": np.array(
                [fake.last_name() for _ in range(_POOL_SIZE)]
            ),
            # De-dup email domains — most locales only have a handful.
            "email_domain": np.array(
                sorted({fake.free_email_domain() for _ in range(500)})
            ),
            "phone": np.array(
                [fake.phone_number() for _ in range(_POOL_SIZE)]
            ),
            "address": np.array(
                [fake.street_address() for _ in range(_POOL_SIZE)]
            ),
            "city": np.array([fake.city() for _ in range(_POOL_SIZE)]),
            "state": np.array(
                [
                    fake.state() if has_state else fake.city()
                    for _ in range(_POOL_SIZE)
                ]
            ),
            "postal_code": np.array(
                [fake.postcode() for _ in range(_POOL_SIZE)]
            ),
        }
    return pools


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_customers() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    n = cfg.NUM_CUSTOMERS

    # ── Faker instances & pools ─────────────────────────────────────
    fakers = {cc: _make_faker(loc, cfg.SEED) for cc, loc in LOCALE_MAP.items()}
    pools = _build_pools(fakers)

    # ── Country assignments (vectorised) ────────────────────────────
    countries = list(cfg.COUNTRIES.keys())
    weights = np.array(list(cfg.COUNTRIES.values()), dtype=np.float64)
    weights /= weights.sum()                     # normalise to be safe
    country_arr = rng.choice(countries, size=n, p=weights)

    # ── Customer IDs ────────────────────────────────────────────────
    customer_ids = np.array([cfg.customer_id(i) for i in range(1, n + 1)])

    # ── Pre-allocate string columns ─────────────────────────────────
    first_names   = np.empty(n, dtype=object)
    last_names    = np.empty(n, dtype=object)
    email_domains = np.empty(n, dtype=object)
    phones        = np.empty(n, dtype=object)
    addresses     = np.empty(n, dtype=object)
    cities        = np.empty(n, dtype=object)
    states        = np.empty(n, dtype=object)
    postal_codes  = np.empty(n, dtype=object)

    # ── Sample from pools per country (vectorised indexing) ─────────
    for cc in tqdm(countries, desc="Sampling per-country fields"):
        mask = country_arr == cc
        cnt = int(mask.sum())
        if cnt == 0:
            continue

        p = pools[cc]

        def _sample(pool: np.ndarray) -> np.ndarray:
            return pool[rng.integers(0, len(pool), size=cnt)]

        first_names[mask]   = _sample(p["first_name"])
        last_names[mask]    = _sample(p["last_name"])
        email_domains[mask] = _sample(p["email_domain"])
        phones[mask]        = _sample(p["phone"])
        addresses[mask]     = _sample(p["address"])
        cities[mask]        = _sample(p["city"])
        states[mask]        = _sample(p["state"])
        postal_codes[mask]  = _sample(p["postal_code"])

    del pools  # free ~80 K strings we no longer need

    # ── Emails (vectorised string ops via pandas) ───────────────────
    row_nums = np.arange(1, n + 1).astype(str)
    emails = (
        pd.Series(first_names, copy=False).str.lower()
        + "."
        + pd.Series(last_names, copy=False).str.lower()
        + pd.Series(row_nums, copy=False)
        + "@"
        + pd.Series(email_domains, copy=False)
    ).values

    # ── Date of birth (vectorised) ──────────────────────────────────
    #   Ages 18–80 relative to the end of the data range.
    min_birth = pd.Timestamp(cfg.END_DATE.year - 80, 1, 1)
    max_birth = pd.Timestamp(cfg.END_DATE.year - 18, 1, 1)
    dob_range_days = (max_birth - min_birth).days
    dobs = min_birth + pd.to_timedelta(
        rng.integers(0, dob_range_days, size=n), unit="D"
    )

    # ── Registration date (vectorised) ──────────────────────────────
    total_days = (cfg.END_DATE - cfg.START_DATE).days
    reg_dates = pd.to_datetime(cfg.START_DATE) + pd.to_timedelta(
        rng.integers(0, total_days, size=n), unit="D"
    )

    # ── Loyalty tier & segment (vectorised) ─────────────────────────
    loyalty = rng.choice(cfg.LOYALTY_TIERS, size=n, p=cfg.LOYALTY_WEIGHTS)
    segment = rng.choice(cfg.CUSTOMER_SEGMENTS, size=n, p=cfg.SEGMENT_WEIGHTS)

    # ── Lifetime value — exponential, scale varies by segment ───────
    _LTV_SCALE = {"Budget": 100.0, "Value": 500.0, "Premium": 2000.0, "Luxury": 8000.0}
    ltv = np.empty(n, dtype=np.float64)
    for seg, scale in _LTV_SCALE.items():
        seg_mask = segment == seg
        ltv[seg_mask] = rng.exponential(scale, size=int(seg_mask.sum()))
    ltv = np.round(ltv, 2)

    # ── is_active (vectorised) ──────────────────────────────────────
    is_active = rng.random(size=n) < 0.90

    # ── Assemble DataFrame ──────────────────────────────────────────
    print("Assembling DataFrame …")
    df = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "first_name": first_names,
            "last_name": last_names,
            "email": emails,
            "phone": phones,
            "address": addresses,
            "city": cities,
            "state": states,
            "country": country_arr,
            "postal_code": postal_codes,
            "date_of_birth": dobs,
            "registration_date": reg_dates,
            "loyalty_tier": loyalty,
            "customer_segment": segment,
            "lifetime_value": ltv,
            "is_active": is_active,
        }
    )

    return df


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating customers …")
    df = generate_customers()
    path = os.path.join(cfg.OUTPUT_DIR, "customers.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {len(df):,} customers → {path}")


if __name__ == "__main__":
    main()
