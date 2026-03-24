"""
Generate product dimension data for Contoso Global Retail.

Output: products.parquet
"""

import os

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg


def generate_products() -> pd.DataFrame:
    rng = np.random.default_rng(cfg.SEED)
    fake = Faker()
    Faker.seed(cfg.SEED)

    categories = list(cfg.PRODUCT_CATEGORIES.keys())
    subcategories = cfg.PRODUCT_CATEGORIES

    # Brand pool per category
    brand_pool = {
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

    rows: list[dict] = []
    for i in range(1, cfg.NUM_PRODUCTS + 1):
        cat = rng.choice(categories)
        subcat = rng.choice(subcategories[cat])
        brand = rng.choice(brand_pool[cat])

        min_cost, max_cost, margin_lo, margin_hi = cfg.CATEGORY_PRICING[cat]
        unit_cost = round(float(rng.uniform(min_cost, max_cost)), 2)
        margin = float(rng.uniform(margin_lo, margin_hi))
        unit_price = round(unit_cost * (1 + margin), 2)

        weight = round(float(rng.uniform(0.1, 30.0)), 2)
        sup_idx = int(rng.integers(1, cfg.NUM_SUPPLIERS + 1))
        created = cfg.START_DATE + pd.Timedelta(
            days=int(rng.integers(0, (cfg.END_DATE - cfg.START_DATE).days))
        )

        # Generate a plausible product name
        adjectives = ["Premium", "Classic", "Ultra", "Pro", "Essential", "Compact", "Deluxe", "Eco"]
        adj = rng.choice(adjectives)
        product_name = f"{brand} {adj} {subcat} {i}"

        rows.append(
            {
                "product_id": cfg.product_id(i),
                "product_name": product_name,
                "category": cat,
                "subcategory": subcat,
                "brand": brand,
                "unit_cost": unit_cost,
                "unit_price": unit_price,
                "weight_kg": weight,
                "supplier_id": cfg.supplier_id(sup_idx),
                "is_active": bool(rng.random() < 0.92),
                "created_date": created,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    print("Generating products …")
    df = generate_products()
    path = os.path.join(cfg.OUTPUT_DIR, "products.parquet")
    df.to_parquet(path, index=False, engine="pyarrow")
    print(f"  ✓ {len(df):,} products → {path}")


if __name__ == "__main__":
    main()
