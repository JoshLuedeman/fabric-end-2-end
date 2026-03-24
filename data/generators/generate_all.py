"""
Orchestrator – run all Tales & Timber data generators in the correct order.

Usage:
    python generate_all.py                          # f8 (default, ~532M rows)
    python generate_all.py --scale f2               # CI / smoke test (~10M)
    python generate_all.py --scale f4               # integration test (~50M)
    python generate_all.py --scale f8               # standard demo (~532M)
    python generate_all.py --scale f16              # large-scale demo (~1B)
    python generate_all.py --scale f32              # enterprise-scale (~3B)
    python generate_all.py --scale f64              # stress-test (~5B)
    python generate_all.py --output-dir /data/demo  # custom output dir
    DATAGEN_OUTPUT_DIR=/data python generate_all.py

Scale profiles are named after the Fabric capacity SKU they target.
"""

import argparse
import os
import sys
import time

# Ensure the generators directory is on sys.path so imports work when
# this script is invoked from any working directory.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import config as cfg


# ---------------------------------------------------------------------------
# Estimated sizes per million rows (approximate Snappy-compressed Parquet)
# ---------------------------------------------------------------------------
_MB_PER_M_ROWS = {
    "customers": 120.0,     # wide dim with strings
    "products": 0.8,        # small dim
    "stores": 0.2,          # small dim
    "employees": 1.0,       # small dim
    "suppliers": 0.1,       # tiny dim
    "warehouses": 0.05,     # tiny dim
    "supply_relationships": 2.0,
    "promotions": 0.5,
    "sales_transactions": 80.0,
    "inventory": 55.0,
    "iot_telemetry": 45.0,
    "shipments": 60.0,
    "web_clickstream": 90.0,
    "customer_interactions": 60.0,
    "promotion_results": 50.0,
}


def _run_step(label: str, fn) -> None:
    """Run a generator function, print progress and elapsed time."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    t0 = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - t0
    print(f"  ⏱  {elapsed:.1f}s")


def _estimate_total_size_gb() -> float:
    """Return a rough estimate of total output size in GB."""
    datasets = {
        "customers": cfg.NUM_CUSTOMERS / 1e6,
        "products": cfg.NUM_PRODUCTS / 1e6,
        "stores": cfg.NUM_STORES / 1e6,
        "employees": cfg.NUM_EMPLOYEES / 1e6,
        "suppliers": cfg.NUM_SUPPLIERS / 1e6,
        "warehouses": cfg.NUM_WAREHOUSES / 1e6,
        "supply_relationships": (cfg.NUM_PRODUCTS * 2) / 1e6,  # ~2 paths per product
        "promotions": cfg.NUM_PROMOTIONS / 1e6,
        "sales_transactions": cfg.NUM_SALES_TRANSACTIONS / 1e6,
        "inventory": cfg.NUM_INVENTORY_RECORDS / 1e6,
        "iot_telemetry": cfg.NUM_IOT_READINGS / 1e6,
        "shipments": cfg.NUM_SHIPMENTS / 1e6,
        "web_clickstream": cfg.NUM_WEB_CLICKSTREAM / 1e6,
        "customer_interactions": cfg.NUM_CUSTOMER_INTERACTIONS / 1e6,
        "promotion_results": cfg.NUM_PROMOTION_RESULTS / 1e6,
    }
    total_mb = sum(
        millions * _MB_PER_M_ROWS.get(name, 50.0)
        for name, millions in datasets.items()
    )
    return total_mb / 1024


def _print_scale_summary() -> None:
    """Print current scale profile and expected row counts."""
    total_rows = (
        cfg.NUM_CUSTOMERS
        + cfg.NUM_PRODUCTS
        + cfg.NUM_STORES
        + cfg.NUM_EMPLOYEES
        + cfg.NUM_SUPPLIERS
        + cfg.NUM_WAREHOUSES
        + cfg.NUM_PROMOTIONS
        + cfg.NUM_SALES_TRANSACTIONS
        + cfg.NUM_INVENTORY_RECORDS
        + cfg.NUM_IOT_READINGS
        + cfg.NUM_SHIPMENTS
        + cfg.NUM_WEB_CLICKSTREAM
        + cfg.NUM_CUSTOMER_INTERACTIONS
        + cfg.NUM_PROMOTION_RESULTS
    )
    est_gb = _estimate_total_size_gb()

    print(f"Scale profile : {cfg.SCALE}")
    print(f"Total rows    : {total_rows:,}")
    print(f"Est. size     : ~{est_gb:.1f} GB (Snappy-compressed Parquet)")
    print()
    print("  Dimensions:")
    print(f"    Customers            {cfg.NUM_CUSTOMERS:>15,}")
    print(f"    Products             {cfg.NUM_PRODUCTS:>15,}")
    print(f"    Stores               {cfg.NUM_STORES:>15,}")
    print(f"    Employees            {cfg.NUM_EMPLOYEES:>15,}")
    print(f"    Suppliers            {cfg.NUM_SUPPLIERS:>15,}")
    print(f"    Warehouses           {cfg.NUM_WAREHOUSES:>15,}")
    print(f"    Promotions           {cfg.NUM_PROMOTIONS:>15,}")
    print("  Facts:")
    print(f"    Sales Transactions   {cfg.NUM_SALES_TRANSACTIONS:>15,}")
    print(f"    Inventory Records    {cfg.NUM_INVENTORY_RECORDS:>15,}")
    print(f"    IoT Readings         {cfg.NUM_IOT_READINGS:>15,}")
    print(f"    Shipments            {cfg.NUM_SHIPMENTS:>15,}")
    print(f"    Web Clickstream      {cfg.NUM_WEB_CLICKSTREAM:>15,}")
    print(f"    Customer Interact.   {cfg.NUM_CUSTOMER_INTERACTIONS:>15,}")
    print(f"    Promotion Results    {cfg.NUM_PROMOTION_RESULTS:>15,}")


def _collect_output_sizes(output_dir: str) -> list[tuple[str, float]]:
    """Walk the output directory and return (name, size_mb) pairs."""
    entries: list[tuple[str, float]] = []
    for item in sorted(os.listdir(output_dir)):
        full = os.path.join(output_dir, item)
        if os.path.isfile(full) and item.endswith(".parquet"):
            size_mb = os.path.getsize(full) / (1024 * 1024)
            entries.append((item, size_mb))
        elif os.path.isdir(full):
            # Sum all parquet files in subdirectory
            dir_size = sum(
                os.path.getsize(os.path.join(full, f))
                for f in os.listdir(full)
                if f.endswith(".parquet")
            )
            n_parts = sum(1 for f in os.listdir(full) if f.endswith(".parquet"))
            size_mb = dir_size / (1024 * 1024)
            entries.append((f"{item}/ ({n_parts} parts)", size_mb))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate all Tales & Timber demo datasets."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for parquet output (default: ./output or DATAGEN_OUTPUT_DIR env var)",
    )
    parser.add_argument(
        "--scale",
        choices=["f2", "f4", "f8", "f16", "f32", "f64"],
        default=None,
        help="Data scale profile named by target Fabric capacity SKU (default: f8). "
             "f2 = ~10M rows / ~1 GB, "
             "f4 = ~50M rows / ~4 GB, "
             "f8 = ~532M rows / ~40 GB, "
             "f16 = ~1B rows / ~80 GB, "
             "f32 = ~3B rows / ~225 GB, "
             "f64 = ~5B rows / ~375 GB.",
    )
    args = parser.parse_args()

    # Apply scale profile BEFORE any generators are imported (they read cfg at import time)
    if args.scale:
        cfg.apply_scale(args.scale)
    elif cfg.SCALE != "f64":
        # Honour DATAGEN_SCALE env var if set
        cfg.apply_scale(cfg.SCALE)

    # Override config output dir if flag is provided
    if args.output_dir:
        cfg.OUTPUT_DIR = args.output_dir

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    print(f"Output directory: {os.path.abspath(cfg.OUTPUT_DIR)}")
    print(f"Seed: {cfg.SEED}")
    print()
    _print_scale_summary()
    print()

    t_total = time.perf_counter()

    # ------------------------------------------------------------------
    # Phase 1 — Dimensions (no cross-dataset dependencies among these)
    # ------------------------------------------------------------------
    from gen_customers import main as gen_customers_main
    from gen_products import main as gen_products_main
    from gen_stores import main as gen_stores_main
    from gen_hr_employees import main as gen_employees_main
    from gen_supply_chain import generate_suppliers, generate_warehouses
    from gen_promotions import generate_promotions

    _run_step("1/13  Customers", gen_customers_main)
    _run_step("2/13  Products", gen_products_main)
    _run_step("3/13  Stores", gen_stores_main)
    _run_step("4/13  Employees", gen_employees_main)

    # Suppliers & warehouses are dimensions generated by the supply-chain module
    def _gen_suppliers_warehouses():
        import pandas as pd
        for name, gen_fn in [
            ("suppliers", generate_suppliers),
            ("warehouses", generate_warehouses),
        ]:
            df = gen_fn()
            path = os.path.join(cfg.OUTPUT_DIR, f"{name}.parquet")
            df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
            print(f"  ✓ {len(df):,} rows → {path}")

    _run_step("5/13  Suppliers & Warehouses", _gen_suppliers_warehouses)

    # Promotions dimension
    def _gen_promotions_dim():
        df = generate_promotions()
        path = os.path.join(cfg.OUTPUT_DIR, "promotions.parquet")
        df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
        print(f"  ✓ {len(df):,} promotions → {path}")

    _run_step("6/13  Promotions (dimension)", _gen_promotions_dim)

    # ------------------------------------------------------------------
    # Phase 2 — Facts (reference dimension IDs)
    # ------------------------------------------------------------------
    from gen_sales_transactions import main as gen_sales_main
    from gen_inventory import main as gen_inventory_main
    from gen_supply_chain import generate_shipments
    from gen_iot_telemetry import main as gen_iot_main
    from gen_web_clickstream import main as gen_clickstream_main
    from gen_customer_interactions import main as gen_interactions_main
    from gen_promotions import generate_promotion_results

    _run_step("7/13  Sales Transactions", gen_sales_main)
    _run_step("8/13  Inventory", gen_inventory_main)

    def _gen_shipments():
        generate_shipments(cfg.OUTPUT_DIR)

    _run_step("9/13  Shipments", _gen_shipments)

    _run_step("10/13  IoT Telemetry", gen_iot_main)
    _run_step("11/13  Web Clickstream", gen_clickstream_main)
    _run_step("12/13  Customer Interactions", gen_interactions_main)

    def _gen_promo_results():
        generate_promotion_results(cfg.OUTPUT_DIR)

    _run_step("13/13  Promotion Results", _gen_promo_results)

    # ------------------------------------------------------------------
    # Supply-chain relationships (dimension-like edges)
    # ------------------------------------------------------------------
    from gen_supply_chain import generate_supply_relationships

    def _gen_sc_rels():
        df = generate_supply_relationships()
        path = os.path.join(cfg.OUTPUT_DIR, "supply_relationships.parquet")
        df.to_parquet(path, index=False, engine="pyarrow", compression="snappy")
        print(f"  ✓ {len(df):,} rows → {path}")

    _run_step("  +  Supply Chain Relationships", _gen_sc_rels)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_elapsed = time.perf_counter() - t_total
    hours = int(total_elapsed // 3600)
    mins = int((total_elapsed % 3600) // 60)
    secs = total_elapsed % 60

    print(f"\n{'='*60}")
    print(f"  ✅  All datasets generated in ", end="")
    if hours:
        print(f"{hours}h {mins}m {secs:.0f}s")
    elif mins:
        print(f"{mins}m {secs:.1f}s")
    else:
        print(f"{secs:.1f}s")
    print(f"  📁  {os.path.abspath(cfg.OUTPUT_DIR)}")
    print(f"  📊  Scale: {cfg.SCALE}")
    print(f"{'='*60}")

    # List generated files/directories with sizes
    entries = _collect_output_sizes(cfg.OUTPUT_DIR)
    total_size_mb = 0.0
    for name, size_mb in entries:
        total_size_mb += size_mb
        if size_mb >= 1024:
            print(f"    {name:<45s} {size_mb / 1024:>8.2f} GB")
        else:
            print(f"    {name:<45s} {size_mb:>8.2f} MB")

    print(f"    {'─'*53}")
    if total_size_mb >= 1024:
        print(f"    {'TOTAL':<45s} {total_size_mb / 1024:>8.2f} GB")
    else:
        print(f"    {'TOTAL':<45s} {total_size_mb:>8.2f} MB")


if __name__ == "__main__":
    main()
