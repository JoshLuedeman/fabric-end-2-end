"""
Shared configuration for Contoso Global Retail & Supply Chain data generators.

All generators import from this module to ensure consistent entity counts,
date ranges, and cross-referenced IDs.

Scale profiles
--------------
* ``small``  – ~865K rows (~43 MB) — fast CI / smoke-test runs
* ``medium`` – ~10M rows — integration testing
* ``full``   – 200M+ fact rows (GB-scale) — realistic demo dataset
"""

import os
from datetime import date

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = 42

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR = os.environ.get("DATAGEN_OUTPUT_DIR", "./output")

# ---------------------------------------------------------------------------
# Chunk size for fact table writers (rows per parquet part file)
# ---------------------------------------------------------------------------
CHUNK_SIZE = 1_000_000

# ---------------------------------------------------------------------------
# Scale profile – set via generate_all.py --scale flag or env var
# ---------------------------------------------------------------------------
SCALE = os.environ.get("DATAGEN_SCALE", "full")  # small | medium | full

# ---------------------------------------------------------------------------
# Entity counts  (dimension tables)
# ---------------------------------------------------------------------------
NUM_CUSTOMERS = 2_000_000
NUM_PRODUCTS = 25_000
NUM_STORES = 500
NUM_EMPLOYEES = 15_000
NUM_SUPPLIERS = 1_000
NUM_WAREHOUSES = 75

# ---------------------------------------------------------------------------
# Volume targets  (fact tables)
# ---------------------------------------------------------------------------
NUM_SALES_TRANSACTIONS = 200_000_000
NUM_INVENTORY_RECORDS = 50_000_000
NUM_IOT_READINGS = 100_000_000
NUM_SHIPMENTS = 2_000_000

# ---------------------------------------------------------------------------
# New dataset targets
# ---------------------------------------------------------------------------
NUM_WEB_CLICKSTREAM = 150_000_000
NUM_CUSTOMER_INTERACTIONS = 10_000_000
NUM_PROMOTIONS = 5_000
NUM_PROMOTION_RESULTS = 20_000_000

# ---------------------------------------------------------------------------
# Date range  (4 years of history)
# ---------------------------------------------------------------------------
START_DATE = date(2022, 1, 1)
END_DATE = date(2025, 12, 31)

# ---------------------------------------------------------------------------
# IoT telemetry window (last 30 days of the overall range)
# ---------------------------------------------------------------------------
IOT_DAYS = 30

# ---------------------------------------------------------------------------
# Country mix (weights for address generation)
# ---------------------------------------------------------------------------
COUNTRIES = {
    "US": 0.30,
    "UK": 0.12,
    "DE": 0.10,
    "JP": 0.08,
    "AU": 0.08,
    "BR": 0.10,
    "IN": 0.12,
    "FR": 0.10,
}

# ---------------------------------------------------------------------------
# Scale profiles — override counts for smaller runs
# ---------------------------------------------------------------------------
_SCALE_PROFILES = {
    "small": {
        "NUM_CUSTOMERS": 50_000,
        "NUM_PRODUCTS": 2_000,
        "NUM_STORES": 150,
        "NUM_EMPLOYEES": 3_000,
        "NUM_SUPPLIERS": 200,
        "NUM_WAREHOUSES": 30,
        "NUM_SALES_TRANSACTIONS": 500_000,
        "NUM_INVENTORY_RECORDS": 100_000,
        "NUM_IOT_READINGS": 200_000,
        "NUM_SHIPMENTS": 3_000,
        "NUM_WEB_CLICKSTREAM": 50_000,
        "NUM_CUSTOMER_INTERACTIONS": 10_000,
        "NUM_PROMOTIONS": 100,
        "NUM_PROMOTION_RESULTS": 5_000,
    },
    "medium": {
        "NUM_CUSTOMERS": 200_000,
        "NUM_PRODUCTS": 5_000,
        "NUM_STORES": 250,
        "NUM_EMPLOYEES": 5_000,
        "NUM_SUPPLIERS": 400,
        "NUM_WAREHOUSES": 40,
        "NUM_SALES_TRANSACTIONS": 5_000_000,
        "NUM_INVENTORY_RECORDS": 1_000_000,
        "NUM_IOT_READINGS": 2_000_000,
        "NUM_SHIPMENTS": 100_000,
        "NUM_WEB_CLICKSTREAM": 2_000_000,
        "NUM_CUSTOMER_INTERACTIONS": 200_000,
        "NUM_PROMOTIONS": 500,
        "NUM_PROMOTION_RESULTS": 500_000,
    },
    # "full" is the default — values already set above
}


def apply_scale(profile: str) -> None:
    """Override module-level counts with a named scale profile."""
    global SCALE
    SCALE = profile
    if profile in _SCALE_PROFILES:
        g = globals()
        for key, value in _SCALE_PROFILES[profile].items():
            g[key] = value

# ---------------------------------------------------------------------------
# Product categories and subcategories
# ---------------------------------------------------------------------------
PRODUCT_CATEGORIES = {
    "Electronics": ["Smartphones", "Laptops", "Tablets", "Headphones", "Cameras", "Smart Home"],
    "Clothing": ["Men's Wear", "Women's Wear", "Children's Wear", "Shoes", "Accessories"],
    "Home & Garden": ["Furniture", "Kitchen", "Bedding", "Garden Tools", "Decor"],
    "Sports": ["Fitness Equipment", "Outdoor Gear", "Team Sports", "Water Sports", "Cycling"],
    "Food & Beverage": ["Snacks", "Beverages", "Organic", "Gourmet", "Pantry Staples"],
    "Health & Beauty": ["Skincare", "Haircare", "Supplements", "Fragrance", "Personal Care"],
    "Toys": ["Action Figures", "Board Games", "Building Sets", "Dolls", "Educational"],
    "Books": ["Fiction", "Non-Fiction", "Children's", "Technical", "Audiobooks"],
    "Automotive": ["Parts", "Accessories", "Tools", "Care Products", "Electronics"],
    "Office": ["Supplies", "Furniture", "Technology", "Breakroom", "Printing"],
}

# Category -> (min_cost, max_cost, margin_low, margin_high)
CATEGORY_PRICING = {
    "Electronics": (20.0, 800.0, 0.15, 0.40),
    "Clothing": (5.0, 150.0, 0.40, 0.70),
    "Home & Garden": (10.0, 500.0, 0.25, 0.55),
    "Sports": (8.0, 400.0, 0.20, 0.50),
    "Food & Beverage": (1.0, 50.0, 0.30, 0.60),
    "Health & Beauty": (3.0, 120.0, 0.45, 0.75),
    "Toys": (5.0, 100.0, 0.35, 0.65),
    "Books": (3.0, 60.0, 0.30, 0.55),
    "Automotive": (5.0, 300.0, 0.20, 0.45),
    "Office": (2.0, 200.0, 0.30, 0.60),
}

# ---------------------------------------------------------------------------
# Loyalty tiers & customer segments
# ---------------------------------------------------------------------------
LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
LOYALTY_WEIGHTS = [0.45, 0.30, 0.18, 0.07]

CUSTOMER_SEGMENTS = ["Budget", "Value", "Premium", "Luxury"]
SEGMENT_WEIGHTS = [0.30, 0.35, 0.25, 0.10]

# ---------------------------------------------------------------------------
# Store types & regions
# ---------------------------------------------------------------------------
STORE_TYPES = ["Flagship", "Standard", "Express", "Outlet", "Online"]
STORE_TYPE_WEIGHTS = [0.05, 0.45, 0.25, 0.15, 0.10]

REGIONS = ["North", "South", "East", "West", "International", "LATAM", "APAC", "EMEA"]

# ---------------------------------------------------------------------------
# Payment & channel
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["Credit Card", "Debit Card", "Cash", "Digital Wallet", "Gift Card"]
PAYMENT_WEIGHTS = [0.35, 0.25, 0.15, 0.15, 0.10]

CHANNELS = ["In-Store", "Online", "Mobile"]
CHANNEL_WEIGHTS = [0.50, 0.30, 0.20]

# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
DEPARTMENTS = ["Sales", "Operations", "Marketing", "IT", "Finance", "HR", "Supply Chain"]

# ---------------------------------------------------------------------------
# Transport modes
# ---------------------------------------------------------------------------
TRANSPORT_MODES = ["Air", "Sea", "Road", "Rail"]
TRANSPORT_WEIGHTS = [0.20, 0.30, 0.35, 0.15]

# ---------------------------------------------------------------------------
# Shipment statuses
# ---------------------------------------------------------------------------
SHIPMENT_STATUSES = ["In Transit", "Delivered", "Delayed", "Cancelled"]
SHIPMENT_STATUS_WEIGHTS = [0.15, 0.65, 0.15, 0.05]

# ---------------------------------------------------------------------------
# IoT sensor types
# ---------------------------------------------------------------------------
SENSOR_TYPES = ["Temperature", "Humidity", "Foot Traffic", "Energy", "Door Counter"]

# ---------------------------------------------------------------------------
# Helper – ID formatters
# ---------------------------------------------------------------------------

def customer_id(n: int) -> str:
    return f"C-{n:07d}"


def product_id(n: int) -> str:
    return f"P-{n:06d}"


def store_id(n: int) -> str:
    return f"S-{n:04d}"


def employee_id(n: int) -> str:
    return f"E-{n:06d}"


def supplier_id(n: int) -> str:
    return f"SUP-{n:04d}"


def warehouse_id(n: int) -> str:
    return f"W-{n:03d}"


def promo_id(n: int) -> str:
    return f"PROMO-{n:05d}"
