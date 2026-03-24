"""
Contoso OLTP Simulator — Configuration

All tuneable parameters for transaction rates, data distributions,
and time-of-day patterns.  Override via environment variables where noted.

ID formats match the data generators (see src/sql-database/seed/):
    Store:    S-{n:04d}
    Product:  P-{n:06d}
    Customer: C-{n:07d}
    Employee: E-{n:06d}
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Rate settings (overridable via env vars)
# ---------------------------------------------------------------------------
TRANSACTION_RATE: float = float(os.getenv("TRANSACTION_RATE", "3.0"))
"""Target POS transactions per second (average, before time-of-day scaling)."""

INTERACTION_RATE: float = float(os.getenv("INTERACTION_RATE", "0.5"))
"""Customer-interaction inserts per second (average)."""

INVENTORY_UPDATE_INTERVAL: int = int(os.getenv("INVENTORY_UPDATE_INTERVAL", "30"))
"""Seconds between batch inventory-replenishment runs."""

STATS_REPORT_INTERVAL: int = int(os.getenv("STATS_REPORT_INTERVAL", "60"))
"""Seconds between stats summaries printed to stdout."""

RATE_MULTIPLIER: float = float(os.getenv("RATE_MULTIPLIER", "1.0"))
"""Global multiplier applied to all rates (useful for load testing)."""

DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
"""When True, log to console instead of writing to the database."""

# ---------------------------------------------------------------------------
# Time-of-day multipliers  (UTC hour → multiplier)
# Peak at lunch (11-13) and dinner (17-19), quiet overnight (2-5)
# ---------------------------------------------------------------------------
TIME_OF_DAY_MULTIPLIER: Dict[int, float] = {
    0: 0.15,
    1: 0.12,
    2: 0.10,
    3: 0.10,
    4: 0.10,
    5: 0.12,
    6: 0.25,
    7: 0.45,
    8: 0.65,
    9: 0.80,
    10: 0.95,
    11: 1.40,   # lunch rush starts
    12: 1.50,   # peak lunch
    13: 1.35,
    14: 1.00,
    15: 0.90,
    16: 0.95,
    17: 1.30,   # dinner rush starts
    18: 1.45,   # peak dinner
    19: 1.25,
    20: 0.85,
    21: 0.55,
    22: 0.35,
    23: 0.20,
}

WEEKEND_MULTIPLIER: float = 1.3
"""Extra multiplier applied on Saturday and Sunday."""

# ---------------------------------------------------------------------------
# Entity ranges
# ---------------------------------------------------------------------------
NUM_STORES: int = int(os.getenv("NUM_STORES", "10"))
"""Number of active store IDs to draw from (S-0001 … S-{n:04d})."""

NUM_PRODUCTS: int = int(os.getenv("NUM_PRODUCTS", "20"))
"""Number of product IDs to draw from (P-000001 … P-{n:06d})."""

NUM_CUSTOMERS: int = int(os.getenv("NUM_CUSTOMERS", "15"))
"""Number of customer IDs to draw from (C-0000001 … C-{n:07d})."""

NUM_EMPLOYEES: int = int(os.getenv("NUM_EMPLOYEES", "10"))
"""Number of employee IDs to draw from (E-000001 … E-{n:06d})."""

# ---------------------------------------------------------------------------
# Store-type weights  (used when picking a random store for a transaction)
# ---------------------------------------------------------------------------
STORE_TYPE_WEIGHTS: Dict[str, float] = {
    "Flagship": 3.0,
    "Standard": 1.0,
    "Express": 0.5,
    "Outlet": 0.7,
    "Online": 2.0,
}

# ---------------------------------------------------------------------------
# Transaction generation
# ---------------------------------------------------------------------------
PAYMENT_METHODS: List[str] = ["Credit Card", "Debit Card", "Cash", "Digital Wallet"]
PAYMENT_WEIGHTS: List[float] = [0.45, 0.25, 0.15, 0.15]

CHANNELS: List[str] = ["In-Store", "Online", "Mobile"]
CHANNEL_WEIGHTS: List[float] = [0.65, 0.25, 0.10]

BASKET_SIZE_BY_CHANNEL: Dict[str, tuple] = {
    "In-Store": (1, 6),    # min, max items
    "Online": (1, 8),
    "Mobile": (1, 4),
}

ANONYMOUS_CUSTOMER_PCT: float = 0.20
"""Probability that a transaction has no customer_id (walk-in)."""

MAX_DISCOUNT_PCT: float = 15.0
"""Upper bound for random per-item discount percentage."""

DISCOUNT_PROBABILITY: float = 0.25
"""Probability that any given line-item gets a discount."""

# ---------------------------------------------------------------------------
# Interaction generation
# ---------------------------------------------------------------------------
INTERACTION_TYPES: List[str] = [
    "phone_call", "email", "web_chat", "in_store",
    "return", "complaint", "feedback",
]
INTERACTION_WEIGHTS: List[float] = [0.20, 0.30, 0.25, 0.15, 0.04, 0.03, 0.03]

INTERACTION_CHANNELS: Dict[str, str] = {
    "phone_call": "phone",
    "email": "email",
    "web_chat": "web",
    "in_store": "store",
    "return": "store",
    "complaint": "email",
    "feedback": "web",
}

INTERACTION_SUBJECTS: Dict[str, List[str]] = {
    "phone_call": [
        "Order status inquiry",
        "Product availability check",
        "Account balance question",
        "Delivery schedule change",
        "Loyalty points inquiry",
    ],
    "email": [
        "Request for product recommendations",
        "Warranty claim submission",
        "Subscription renewal query",
        "Billing discrepancy report",
        "Store hours inquiry",
    ],
    "web_chat": [
        "Live order tracking",
        "Size/fit guidance",
        "Return policy question",
        "Promo code not working",
        "Password reset help",
    ],
    "in_store": [
        "Personal shopping assistance",
        "Gift wrapping request",
        "Product demonstration",
        "Price match request",
        "Loyalty enrollment",
    ],
    "return": [
        "Defective item return",
        "Wrong size exchange",
        "Changed mind — full return",
        "Duplicate order return",
    ],
    "complaint": [
        "Late delivery complaint",
        "Damaged packaging complaint",
        "Rude staff complaint",
    ],
    "feedback": [
        "Positive store experience",
        "Website usability suggestion",
        "New product request",
    ],
}

RESOLUTION_STATUSES: List[str] = ["resolved", "pending", "escalated"]
RESOLUTION_WEIGHTS: List[float] = [0.70, 0.20, 0.10]

# ---------------------------------------------------------------------------
# Inventory replenishment
# ---------------------------------------------------------------------------
REPLENISHMENT_STORE_PCT: float = 0.30
"""Fraction of stores that receive a shipment each cycle."""

REPLENISHMENT_QTY_RANGE: tuple = (20, 200)
"""Min/max units added per (store, product) replenishment."""

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
SQL_CONNECTION_STRING: str = os.getenv("SQL_CONNECTION_STRING", "")
"""ODBC connection string for Fabric SQL Database."""


# ---------------------------------------------------------------------------
# Helper: generate ID lists
# ---------------------------------------------------------------------------
def store_ids() -> List[str]:
    """Return list of store IDs matching seed format S-{n:04d}."""
    return [f"S-{i:04d}" for i in range(1, NUM_STORES + 1)]


def product_ids() -> List[str]:
    """Return list of product IDs matching seed format P-{n:06d}."""
    return [f"P-{i:06d}" for i in range(1, NUM_PRODUCTS + 1)]


def customer_ids() -> List[str]:
    """Return list of customer IDs matching seed format C-{n:07d}."""
    return [f"C-{i:07d}" for i in range(1, NUM_CUSTOMERS + 1)]


def employee_ids() -> List[str]:
    """Return list of employee IDs matching seed format E-{n:06d}."""
    return [f"E-{i:06d}" for i in range(1, NUM_EMPLOYEES + 1)]
