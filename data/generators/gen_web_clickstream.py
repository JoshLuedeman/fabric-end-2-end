"""
Generate web clickstream event data for Tales & Timber.

Output: output/web_clickstream/part_XXXXXXXXXX.parquet  (chunked, Snappy-compressed)

Generates ``cfg.NUM_WEB_CLICKSTREAM`` rows (default 150 M) in chunks of
``cfg.CHUNK_SIZE`` (default 1 M) so that peak memory stays bounded regardless
of total volume.  Each chunk is fully vectorised with NumPy.

Fields include session-grouped events with realistic browsing patterns:
sessions of 10–30 events, ~40 % anonymous traffic, ~70 % cart-abandonment
rate, and traffic weighted toward business hours / weekends.
"""

from __future__ import annotations

import os
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import config as cfg

# ── Constants ─────────────────────────────────────────────────────────────
EVENT_TYPES = ["page_view", "search", "add_to_cart", "remove_from_cart",
               "checkout", "purchase"]
EVENT_WEIGHTS = np.array([0.45, 0.20, 0.15, 0.05, 0.08, 0.07])

REFERRERS = ["google", "facebook", "instagram", "direct", "email",
             "bing", "twitter", "affiliate"]
REFERRER_WEIGHTS = np.array([0.30, 0.15, 0.10, 0.20, 0.10, 0.05, 0.05, 0.05])

DEVICE_TYPES = ["desktop", "mobile", "tablet"]
DEVICE_WEIGHTS = np.array([0.40, 0.45, 0.15])

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge", "Samsung Internet"]
BROWSER_WEIGHTS = np.array([0.50, 0.25, 0.10, 0.10, 0.05])

SEARCH_TERMS = [
    "laptop", "phone", "headphones", "shoes", "watch",
    "camera", "tablet", "dress", "tv", "jacket",
    "backpack", "keyboard", "monitor", "speaker", "charger",
]

COUNTRY_CITIES: dict[str, list[str]] = {
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
    "DE": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
    "JP": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Sapporo"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "BR": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza"],
    "IN": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
    "FR": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
}

# Hour-of-day weights: business hours (9–21) get 3× base traffic.
_HOUR_WEIGHTS = np.ones(24)
_HOUR_WEIGHTS[9:21] = 3.0
_HOUR_WEIGHTS /= _HOUR_WEIGHTS.sum()

# ── Arrow schema (defined once so every part file is identical) ───────────
_ARROW_SCHEMA = pa.schema(
    [
        pa.field("event_id", pa.string()),
        pa.field("session_id", pa.string()),
        pa.field("customer_id", pa.string()),          # nullable
        pa.field("event_type", pa.string()),
        pa.field("page_url", pa.string()),
        pa.field("product_id", pa.string()),            # nullable
        pa.field("referrer", pa.string()),
        pa.field("device_type", pa.string()),
        pa.field("browser", pa.string()),
        pa.field("geo_country", pa.string()),
        pa.field("geo_city", pa.string()),
        pa.field("timestamp", pa.timestamp("us")),
        pa.field("duration_seconds", pa.int32()),
    ]
)


# ── Helpers ───────────────────────────────────────────────────────────────
def _vectorised_uuids(rng: np.random.Generator, n: int) -> list[str]:
    """Return *n* UUID-v4-style strings seeded from *rng*."""
    raw = rng.bytes(16 * n)
    return [str(uuid.UUID(bytes=raw[i * 16 : (i + 1) * 16])) for i in range(n)]


def _build_sessions(
    rng: np.random.Generator, chunk_size: int
) -> tuple[np.ndarray, int]:
    """Partition *chunk_size* events into sessions of 10–30 events.

    Returns ``(session_lens, n_sessions)`` where
    ``session_lens.sum() == chunk_size``.
    """
    # Over-allocate using minimum session length as divisor.
    n_alloc = chunk_size // 10 + 2
    lens = rng.integers(10, 31, size=n_alloc)
    cum = np.cumsum(lens)

    # First index where cumulative sum >= chunk_size.
    idx = int(np.searchsorted(cum, chunk_size, side="left"))
    n_sessions = idx + 1
    session_lens = lens[:n_sessions].copy()

    # Trim last session so the total equals chunk_size exactly.
    session_lens[-1] -= int(cum[idx] - chunk_size)
    if session_lens[-1] <= 0:
        session_lens = session_lens[:-1]
        n_sessions -= 1

    return session_lens, n_sessions


# ── Chunk generator ──────────────────────────────────────────────────────
def _generate_chunk(chunk_idx: int, chunk_size: int) -> pa.Table:
    """Build one chunk as a PyArrow Table (fully vectorised)."""
    rng = np.random.default_rng(cfg.SEED + chunk_idx)

    country_codes = list(cfg.COUNTRIES.keys())
    country_weights = np.array(list(cfg.COUNTRIES.values()))
    country_weights /= country_weights.sum()

    total_days = (cfg.END_DATE - cfg.START_DATE).days + 1

    # ── Sessions ──────────────────────────────────────────────────────
    session_lens, n_sessions = _build_sessions(rng, chunk_size)
    session_idx = np.repeat(np.arange(n_sessions), session_lens)

    session_uuids = _vectorised_uuids(rng, n_sessions)

    # ── Event IDs (one per row) ───────────────────────────────────────
    event_ids = _vectorised_uuids(rng, chunk_size)

    # ── Session-level attributes ──────────────────────────────────────
    # Customer: 60 % logged-in, 40 % anonymous (null).
    s_customer_nums = rng.integers(1, cfg.NUM_CUSTOMERS + 1, size=n_sessions)
    s_anonymous = rng.random(n_sessions) < 0.40
    s_customer_ids = np.array(
        [cfg.customer_id(int(n)) for n in s_customer_nums], dtype=object,
    )
    s_customer_ids[s_anonymous] = None

    # Device, browser, referrer (constant within a session).
    s_devices = rng.choice(DEVICE_TYPES, size=n_sessions, p=DEVICE_WEIGHTS)
    s_browsers = rng.choice(BROWSERS, size=n_sessions, p=BROWSER_WEIGHTS)
    s_referrers = rng.choice(REFERRERS, size=n_sessions, p=REFERRER_WEIGHTS)

    # Geo (country → city).
    s_countries = rng.choice(country_codes, size=n_sessions, p=country_weights)
    s_cities = np.array(
        [rng.choice(COUNTRY_CITIES[c]) for c in s_countries],
    )

    # Expand session-level → event-level via session_idx.
    session_ids = np.array(session_uuids, dtype=object)[session_idx]
    customer_ids = s_customer_ids[session_idx]
    devices = s_devices[session_idx]
    browsers = s_browsers[session_idx]
    referrers = s_referrers[session_idx]
    countries = s_countries[session_idx]
    cities = s_cities[session_idx]

    # ── Event types ───────────────────────────────────────────────────
    event_types = rng.choice(EVENT_TYPES, size=chunk_size, p=EVENT_WEIGHTS)

    # Cart abandonment: 70 % of sessions with add_to_cart never purchase.
    has_cart = np.zeros(n_sessions, dtype=bool)
    np.maximum.at(has_cart, session_idx, event_types == "add_to_cart")
    abandon = has_cart & (rng.random(n_sessions) < 0.70)
    abandon_expanded = abandon[session_idx]
    purchase_in_abandon = (event_types == "purchase") & abandon_expanded
    event_types = event_types.copy()          # writeable array
    event_types[purchase_in_abandon] = "page_view"

    # ── Product numbers (shared by page_url & product_id columns) ─────
    product_nums = rng.integers(1, cfg.NUM_PRODUCTS + 1, size=chunk_size)
    product_strs = np.array([cfg.product_id(int(n)) for n in product_nums])

    # ── Page URLs (driven by final event_type) ────────────────────────
    page_urls = np.empty(chunk_size, dtype=object)

    pv_mask = event_types == "page_view"
    page_urls[pv_mask] = np.array(
        [f"/products/{pid}" for pid in product_strs[pv_mask]],
    )

    search_mask = event_types == "search"
    search_terms = rng.choice(SEARCH_TERMS, size=int(search_mask.sum()))
    page_urls[search_mask] = np.array(
        [f"/search?q={t}" for t in search_terms],
    )

    atc_mask = event_types == "add_to_cart"
    page_urls[atc_mask] = np.array(
        [f"/products/{pid}" for pid in product_strs[atc_mask]],
    )

    page_urls[event_types == "remove_from_cart"] = "/cart"
    page_urls[event_types == "checkout"] = "/checkout"
    page_urls[event_types == "purchase"] = "/checkout/confirm"

    # ── Product IDs (null for search & home pages → ~30 % overall) ───
    product_ids = np.array(
        [cfg.product_id(int(n)) for n in product_nums], dtype=object,
    )
    null_product_mask = event_types == "search"
    # Also null ~22 % of page_views (browsing home / category pages)
    # so the overall null rate lands near 30 %.
    pv_null = pv_mask & (rng.random(chunk_size) < 0.22)
    null_product_mask = null_product_mask | pv_null
    product_ids[null_product_mask] = None

    # Rewrite those page_view URLs to "/" (home page).
    page_urls[pv_null] = "/"

    # ── Timestamps (weighted toward business hours & weekends) ────────
    start_dow = cfg.START_DATE.weekday()           # 0 = Monday
    day_of_week = (np.arange(total_days) + start_dow) % 7
    day_weights = np.ones(total_days)
    day_weights[day_of_week >= 5] = 1.3            # weekend boost
    day_weights /= day_weights.sum()
    day_offsets = rng.choice(total_days, size=chunk_size, p=day_weights)

    hours = rng.choice(24, size=chunk_size, p=_HOUR_WEIGHTS)
    minutes = rng.integers(0, 60, size=chunk_size)
    seconds = rng.integers(0, 60, size=chunk_size)

    base_ts = np.datetime64(cfg.START_DATE, "us")
    timestamps = (
        base_ts
        + day_offsets.astype("timedelta64[D]")
        + hours.astype("timedelta64[h]")
        + minutes.astype("timedelta64[m]")
        + seconds.astype("timedelta64[s]")
    )

    # ── Duration (page_view ~30 s mean, actions ~5 s mean) ────────────
    durations = np.empty(chunk_size, dtype=np.int32)
    durations[pv_mask] = np.clip(
        rng.exponential(30.0, size=int(pv_mask.sum())).astype(np.int32),
        1, 300,
    )
    action_mask = ~pv_mask
    durations[action_mask] = np.clip(
        rng.exponential(5.0, size=int(action_mask.sum())).astype(np.int32),
        1, 300,
    )

    # ── Assemble Arrow Table ──────────────────────────────────────────
    table = pa.table(
        {
            "event_id": event_ids,
            "session_id": pa.array(session_ids.tolist(), type=pa.string()),
            "customer_id": pa.array(customer_ids.tolist(), type=pa.string()),
            "event_type": event_types.tolist(),
            "page_url": pa.array(page_urls.tolist(), type=pa.string()),
            "product_id": pa.array(product_ids.tolist(), type=pa.string()),
            "referrer": referrers.tolist(),
            "device_type": devices.tolist(),
            "browser": browsers.tolist(),
            "geo_country": countries.tolist(),
            "geo_city": cities.tolist(),
            "timestamp": timestamps,
            "duration_seconds": durations,
        },
        schema=_ARROW_SCHEMA,
    )
    return table


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    total = cfg.NUM_WEB_CLICKSTREAM
    chunk_size = cfg.CHUNK_SIZE
    num_chunks = (total + chunk_size - 1) // chunk_size  # ceiling division

    out_dir = os.path.join(cfg.OUTPUT_DIR, "web_clickstream")
    os.makedirs(out_dir, exist_ok=True)

    print(
        f"Generating {total:,} web clickstream events "
        f"({num_chunks} chunks × {chunk_size:,}) → {out_dir}"
    )

    rows_written = 0
    for chunk_idx in tqdm(range(num_chunks), desc="web_clickstream", unit="chunk"):
        remaining = total - rows_written
        current_size = min(chunk_size, remaining)

        table = _generate_chunk(chunk_idx, current_size)

        part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
        pq.write_table(table, part_path, compression="snappy")

        rows_written += current_size

    print(
        f"  ✓ {rows_written:,} clickstream events → {out_dir}/ "
        f"({num_chunks} part files)"
    )


if __name__ == "__main__":
    main()
