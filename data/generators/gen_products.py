"""
Generate product dimension data for Contoso Global Retail.

Output: products.parquet  (snappy-compressed)
"""

import os

import numpy as np
import pandas as pd

import config as cfg

# ── Brand pool per category (kept in sync with cfg.PRODUCT_CATEGORIES) ──────
BRAND_POOL: dict[str, list[str]] = {
    "Electronics": ["TechNova", "VoltEdge", "PixelPro", "CoreWave", "NeoSync"],
    "Clothing": ["UrbanThread", "StyleCraft", "VelvetLine", "PrimeFit", "AuraWear"],
    "Home & Garden": ["HomeNest", "GreenHaven", "CozyCraft", "BrightSpace", "NaturEdge"],
    "Sports": ["PeakForce", "TrailBlazer", "IronPulse", "FlexMotion", "AquaDrive"],
    "Food & Beverage": ["FreshVista", "GoldenHarvest", "PureBite", "TasteWell", "NutriCore"],
    "Health & Beauty": ["GlowEssence", "VitalBloom", "PureRadiance", "ZenCare", "LuxeDerm"],
    "Toys": ["FunSpark", "PlayMakers", "DreamBuild", "TinyWorld", "JoyFactory"],
    "Books": ["PageTurn", "InkWell", "StoryForge", "MindPress", "NovelEdge"],
    "Automotive": ["DriveForce", "AutoElite", "RoadMaster", "TurboFit", "GearPro"],
    "Office": ["DeskPrime", "WorkFlow", "PaperTrail", "ProDesk", "SmartOffice"],
}

_ADJECTIVES = np.array(
    ["Premium", "Classic", "Ultra", "Pro", "Essential", "Compact", "Deluxe", "Eco"]
)


def generate_products() -> pd.DataFrame:
    """Return a DataFrame of *cfg.NUM_PRODUCTS* product rows.

    All columns are built from vectorised numpy arrays rather than a
    row-by-row Python loop so that 25 000 rows generate in milliseconds.
    """
    n = cfg.NUM_PRODUCTS
    rng = np.random.default_rng(cfg.SEED)

    categories = list(cfg.PRODUCT_CATEGORIES.keys())
    num_cats = len(categories)

    # ── 1. Assign a category to every product (uniform) ─────────────────
    cat_indices = rng.integers(0, num_cats, size=n)
    cat_array = np.array(categories, dtype=object)[cat_indices]

    # ── 2. Per-category vectorised draws (subcat, brand, pricing) ───────
    subcat_array = np.empty(n, dtype=object)
    brand_array = np.empty(n, dtype=object)
    unit_costs = np.empty(n, dtype=np.float64)
    margins = np.empty(n, dtype=np.float64)

    for cat_idx, cat in enumerate(categories):
        mask = cat_indices == cat_idx
        count = int(mask.sum())
        if count == 0:
            continue

        subs = np.array(cfg.PRODUCT_CATEGORIES[cat], dtype=object)
        subcat_array[mask] = subs[rng.integers(0, len(subs), size=count)]

        brands = np.array(BRAND_POOL[cat], dtype=object)
        brand_array[mask] = brands[rng.integers(0, len(brands), size=count)]

        min_cost, max_cost, margin_lo, margin_hi = cfg.CATEGORY_PRICING[cat]
        unit_costs[mask] = rng.uniform(min_cost, max_cost, size=count)
        margins[mask] = rng.uniform(margin_lo, margin_hi, size=count)

    unit_costs = np.round(unit_costs, 2)
    unit_prices = np.round(unit_costs * (1 + margins), 2)

    # ── 3. Remaining scalar columns (all vectorised) ────────────────────
    weights = np.round(rng.uniform(0.1, 30.0, size=n), 2)
    supplier_indices = rng.integers(1, cfg.NUM_SUPPLIERS + 1, size=n)
    is_active = rng.random(size=n) < 0.92

    total_days = (cfg.END_DATE - cfg.START_DATE).days
    day_offsets = rng.integers(0, total_days, size=n)
    created_dates = pd.to_datetime(cfg.START_DATE) + pd.to_timedelta(
        day_offsets, unit="D"
    )

    adj_array = _ADJECTIVES[rng.integers(0, len(_ADJECTIVES), size=n)]

    # ── 4. String ID / name columns ─────────────────────────────────────
    ids = np.arange(1, n + 1)
    product_ids = np.array([cfg.product_id(i) for i in ids])
    supplier_ids = np.array([cfg.supplier_id(int(s)) for s in supplier_indices])
    product_names = np.array(
        [
            f"{b} {a} {sc} {i}"
            for b, a, sc, i in zip(brand_array, adj_array, subcat_array, ids)
        ]
    )

    # ── 5. Assemble DataFrame ───────────────────────────────────────────
    return pd.DataFrame(
        {
            "product_id": product_ids,
            "product_name": product_names,
            "category": cat_array,
            "subcategory": subcat_array,
            "brand": brand_array,
            "unit_cost": unit_costs,
            "unit_price": unit_prices,
            "weight_kg": weights,
            "supplier_id": supplier_ids,
            "is_active": is_active,
            "created_date": created_dates,
        }
    )


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating products …")
    df = generate_products()
    path = os.path.join(cfg.OUTPUT_DIR, "products.parquet")
    df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
    print(f"  ✓ {len(df):,} products → {path}")


if __name__ == "__main__":
    main()
