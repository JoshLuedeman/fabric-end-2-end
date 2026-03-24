"""
Shared configuration for Contoso Global Retail & Supply Chain data generators.

All generators import from this module to ensure consistent entity counts,
date ranges, and cross-referenced IDs.
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
# Entity counts
# ---------------------------------------------------------------------------
NUM_CUSTOMERS = 50_000
NUM_PRODUCTS = 2_000
NUM_STORES = 150
NUM_EMPLOYEES = 3_000
NUM_SUPPLIERS = 200
NUM_WAREHOUSES = 30

# ---------------------------------------------------------------------------
# Volume targets
# ---------------------------------------------------------------------------
NUM_SALES_TRANSACTIONS = 500_000
NUM_INVENTORY_RECORDS = 100_000
NUM_IOT_READINGS = 200_000

# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------
START_DATE = date(2023, 1, 1)
END_DATE = date(2025, 12, 31)

# ---------------------------------------------------------------------------
# IoT telemetry window (last 30 days of the overall range)
# ---------------------------------------------------------------------------
IOT_DAYS = 30

# ---------------------------------------------------------------------------
# Country mix (weights for address generation)
# ---------------------------------------------------------------------------
COUNTRIES = {
    "US": 0.40,
    "UK": 0.20,
    "DE": 0.15,
    "JP": 0.10,
    "AU": 0.15,
}

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

REGIONS = ["North", "South", "East", "West", "International"]

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
    return f"C-{n:06d}"

def product_id(n: int) -> str:
    return f"P-{n:06d}"

def store_id(n: int) -> str:
    return f"S-{n:03d}"

def employee_id(n: int) -> str:
    return f"E-{n:05d}"

def supplier_id(n: int) -> str:
    return f"SUP-{n:03d}"

def warehouse_id(n: int) -> str:
    return f"W-{n:02d}"
