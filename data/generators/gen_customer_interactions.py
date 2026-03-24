"""
Generate CRM / customer-service interaction data for Tales & Timber.

Output: output/customer_interactions/part_XXXXXXXXXX.parquet  (chunked, Snappy-compressed)

Generates ``cfg.NUM_CUSTOMER_INTERACTIONS`` rows (default 10 M) in chunks of
``cfg.CHUNK_SIZE`` (default 1 M) so that peak memory stays bounded regardless
of total volume.  Each chunk is fully vectorised with NumPy.

Seasonal patterns
-----------------
* Higher overall volume in Nov / Dec / Jan (holiday season).
* Complaints spike in Jan (post-holiday).
* Return requests cluster in Jan–Feb.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import config as cfg

# ── Constants ─────────────────────────────────────────────────────────────
INTERACTION_TYPES = ["phone_call", "email", "chat", "in_store", "return", "complaint", "feedback"]
INTERACTION_WEIGHTS = np.array([0.20, 0.25, 0.20, 0.10, 0.10, 0.10, 0.05])

CHANNELS = ["phone", "email", "web_chat", "social_media", "in_store"]
CHANNEL_WEIGHTS = np.array([0.25, 0.30, 0.20, 0.10, 0.15])

SUBJECT_CATEGORIES = [
    "billing", "product_inquiry", "return_request", "technical_support",
    "complaint", "feedback", "order_status",
]
SUBJECT_WEIGHTS = np.array([0.15, 0.25, 0.15, 0.15, 0.10, 0.05, 0.15])

RESOLUTION_STATUSES = ["resolved", "pending", "escalated", "unresolved"]
RESOLUTION_WEIGHTS = np.array([0.60, 0.15, 0.15, 0.10])

# Duration ranges (min, max inclusive) in minutes per interaction type
_DURATION_RANGES: dict[str, tuple[int, int]] = {
    "phone_call": (5, 45),
    "email":      (1, 5),
    "chat":       (3, 30),
    "in_store":   (5, 60),
    "return":     (5, 30),
    "complaint":  (10, 60),
    "feedback":   (2, 15),
}

# Satisfaction score distribution (1–5), biased toward 3-4
_SATISFACTION_SCORES = np.array([1, 2, 3, 4, 5], dtype=np.int8)
_SATISFACTION_WEIGHTS = np.array([0.05, 0.10, 0.30, 0.35, 0.20])

# Monthly volume multipliers (index 1–12)
_MONTHLY_VOLUME: dict[int, float] = {
    1:  1.50,   # Jan – post-holiday returns & complaints
    2:  1.10,   # Feb – tail of return season
    3:  1.00,
    4:  1.00,
    5:  1.00,
    6:  1.00,
    7:  1.00,
    8:  1.00,
    9:  1.00,
    10: 1.00,
    11: 1.30,   # Nov – pre-holiday
    12: 1.80,   # Dec – holiday peak
}

# Arrow schema – defined once so every part file is identical.
_ARROW_SCHEMA = pa.schema(
    [
        pa.field("interaction_id",    pa.string()),
        pa.field("customer_id",       pa.string()),
        pa.field("interaction_type",  pa.string()),
        pa.field("channel",           pa.string()),
        pa.field("subject_category",  pa.string()),
        pa.field("resolution_status", pa.string()),
        pa.field("agent_employee_id", pa.string()),
        pa.field("store_id",          pa.string()),          # nullable
        pa.field("satisfaction_score", pa.int8()),            # nullable
        pa.field("duration_minutes",  pa.int16()),
        pa.field("created_at",        pa.timestamp("us")),
        pa.field("resolved_at",       pa.timestamp("us")),   # nullable
    ]
)


# ── Pre-computed date look-ups ────────────────────────────────────────────

def _precompute_day_metadata() -> tuple[np.ndarray, np.ndarray]:
    """Return *(day_weights, day_months)* arrays spanning the full date range.

    * *day_weights* – normalised probability vector (one entry per calendar day).
    * *day_months*  – month number (1-12) for each calendar day offset.
    """
    total_days = (cfg.END_DATE - cfg.START_DATE).days + 1
    months = np.array(
        [(cfg.START_DATE + timedelta(days=d)).month for d in range(total_days)],
        dtype=np.int32,
    )
    # Build look-up: index 0 unused, indices 1-12 → monthly multiplier
    weight_lookup = np.zeros(13, dtype=np.float64)
    for m in range(1, 13):
        weight_lookup[m] = _MONTHLY_VOLUME[m]
    weights = weight_lookup[months]
    weights /= weights.sum()
    return weights, months


# ── Helpers ───────────────────────────────────────────────────────────────

def _vectorised_uuids(rng: np.random.Generator, n: int) -> list[str]:
    """Return *n* UUID-v4-style strings seeded from *rng*."""
    raw = rng.bytes(16 * n)
    return [str(uuid.UUID(bytes=raw[i * 16 : (i + 1) * 16])) for i in range(n)]


def _generate_chunk(
    chunk_idx: int,
    chunk_size: int,
    day_weights: np.ndarray,
    day_months: np.ndarray,
) -> pa.Table:
    """Build one chunk as a PyArrow Table (fully vectorised)."""
    rng = np.random.default_rng(cfg.SEED + chunk_idx)
    total_days = len(day_weights)

    # ── IDs ───────────────────────────────────────────────────────────
    interaction_ids = _vectorised_uuids(rng, chunk_size)

    customer_nums = rng.integers(1, cfg.NUM_CUSTOMERS + 1, size=chunk_size)
    customer_ids = np.array([cfg.customer_id(int(n)) for n in customer_nums])

    agent_nums = rng.integers(1, cfg.NUM_EMPLOYEES + 1, size=chunk_size)
    agent_ids = np.array([cfg.employee_id(int(n)) for n in agent_nums])

    # ── Dates with seasonal weighting ─────────────────────────────────
    day_offsets = rng.choice(total_days, size=chunk_size, p=day_weights)
    months = day_months[day_offsets]

    # Timestamp = base date + day-offset (seconds) + random second-of-day [08:00, 22:00)
    second_of_day = rng.integers(8 * 3600, 22 * 3600, size=chunk_size)
    base_ts = np.datetime64(cfg.START_DATE, "s")
    total_seconds = day_offsets.astype(np.int64) * 86400 + second_of_day.astype(np.int64)
    created_at = base_ts + total_seconds.astype("timedelta64[s]")

    # ── Categorical columns ───────────────────────────────────────────
    interaction_types = rng.choice(INTERACTION_TYPES, size=chunk_size, p=INTERACTION_WEIGHTS)
    channels          = rng.choice(CHANNELS, size=chunk_size, p=CHANNEL_WEIGHTS)
    subject_cats      = rng.choice(SUBJECT_CATEGORIES, size=chunk_size, p=SUBJECT_WEIGHTS)
    resolution_stats  = rng.choice(RESOLUTION_STATUSES, size=chunk_size, p=RESOLUTION_WEIGHTS)

    # ── Seasonal overrides ────────────────────────────────────────────
    # Complaints spike in January (~25 % of Jan rows overridden)
    jan_idx = np.where(months == 1)[0]
    if len(jan_idx):
        flip = rng.random(len(jan_idx)) < 0.25
        interaction_types[jan_idx[flip]] = "complaint"

    # Returns cluster in Jan–Feb (~20 % of remaining Jan/Feb rows)
    jan_feb_remaining = np.where((months <= 2) & (interaction_types != "complaint"))[0]
    if len(jan_feb_remaining):
        flip = rng.random(len(jan_feb_remaining)) < 0.20
        interaction_types[jan_feb_remaining[flip]] = "return"

    # ── Store ID (nullable – ~60 % null for non-store interactions) ───
    store_nums = rng.integers(1, cfg.NUM_STORES + 1, size=chunk_size)
    store_ids = np.array([cfg.store_id(int(n)) for n in store_nums])
    store_null_mask = rng.random(chunk_size) < 0.60
    store_id_arr = pa.array(store_ids.tolist(), type=pa.string(), mask=store_null_mask)

    # ── Satisfaction score (nullable – ~30 % null, biased toward 3-4) ─
    scores = rng.choice(_SATISFACTION_SCORES, size=chunk_size, p=_SATISFACTION_WEIGHTS)
    score_null_mask = rng.random(chunk_size) < 0.30
    satisfaction_arr = pa.array(scores.tolist(), type=pa.int8(), mask=score_null_mask)

    # ── Duration minutes (varies by interaction type) ─────────────────
    duration = np.zeros(chunk_size, dtype=np.int16)
    for itype, (lo, hi) in _DURATION_RANGES.items():
        mask = interaction_types == itype
        count = mask.sum()
        if count:
            duration[mask] = rng.integers(lo, hi + 1, size=count).astype(np.int16)

    # ── Resolved-at (nullable: null for pending / unresolved) ─────────
    resolved_offset_s = np.zeros(chunk_size, dtype=np.int64)

    mask_resolved = resolution_stats == "resolved"
    if mask_resolved.any():
        # Resolved within 0–48 hours
        resolved_offset_s[mask_resolved] = rng.integers(
            0, 48 * 3600 + 1, size=mask_resolved.sum(),
        )

    mask_escalated = resolution_stats == "escalated"
    if mask_escalated.any():
        # Escalated: resolved in 1–14 days
        resolved_offset_s[mask_escalated] = rng.integers(
            24 * 3600, 14 * 24 * 3600 + 1, size=mask_escalated.sum(),
        )

    resolved_at = created_at + resolved_offset_s.astype("timedelta64[s]")
    resolved_null = (resolution_stats == "pending") | (resolution_stats == "unresolved")
    resolved_at_arr = pa.array(
        resolved_at.astype("datetime64[us]"),
        type=pa.timestamp("us"),
        mask=resolved_null,
    )

    # ── Assemble Arrow Table ──────────────────────────────────────────
    table = pa.table(
        {
            "interaction_id":    interaction_ids,
            "customer_id":       customer_ids,
            "interaction_type":  interaction_types,
            "channel":           channels,
            "subject_category":  subject_cats,
            "resolution_status": resolution_stats,
            "agent_employee_id": agent_ids,
            "store_id":          store_id_arr,
            "satisfaction_score": satisfaction_arr,
            "duration_minutes":  duration,
            "created_at":        created_at.astype("datetime64[us]"),
            "resolved_at":       resolved_at_arr,
        },
        schema=_ARROW_SCHEMA,
    )
    return table


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    total = cfg.NUM_CUSTOMER_INTERACTIONS
    chunk_size = cfg.CHUNK_SIZE
    num_chunks = (total + chunk_size - 1) // chunk_size

    out_dir = os.path.join(cfg.OUTPUT_DIR, "customer_interactions")
    os.makedirs(out_dir, exist_ok=True)

    print(
        f"Generating {total:,} customer interaction records "
        f"({num_chunks} chunks × {chunk_size:,}) → {out_dir}"
    )

    # Pre-compute seasonal day weights and month look-up (once)
    day_weights, day_months = _precompute_day_metadata()

    rows_written = 0
    for chunk_idx in tqdm(range(num_chunks), desc="customer_interactions", unit="chunk"):
        remaining = total - rows_written
        current_size = min(chunk_size, remaining)

        table = _generate_chunk(chunk_idx, current_size, day_weights, day_months)

        part_path = os.path.join(out_dir, f"part_{chunk_idx:010d}.parquet")
        pq.write_table(table, part_path, compression="snappy")

        rows_written += current_size

    print(
        f"  ✓ {rows_written:,} customer interaction records → {out_dir}/ "
        f"({num_chunks} part files)"
    )


if __name__ == "__main__":
    main()
