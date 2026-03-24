# Fabric Notebook: Silver – Transform Supply Chain Tables
# Transforms bronze suppliers, warehouses, shipments, inventory,
# and supply_relationships.

from pyspark.sql.functions import *

# ═══════════════════════════════════════════════
#  SUPPLIERS
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing suppliers...")
print("=" * 50)

df_sup_raw = spark.read.format("delta").table("bronze_suppliers")
total_sup = df_sup_raw.count()
print(f"  Rows read: {total_sup}")

# Trim string fields
df_sup = (
    df_sup_raw
    .withColumn("supplier_name", trim(col("supplier_name")))
    .withColumn("contact_name", trim(col("contact_name")))
    .withColumn("contact_email", trim(col("contact_email")))
    .withColumn("phone", trim(col("phone")))
    .withColumn("country", initcap(lower(trim(col("country")))))
    .withColumn("city", initcap(lower(trim(col("city")))))
)

# Validate reliability_score between 0 and 1 (clamp)
df_sup = df_sup.withColumn(
    "reliability_score",
    when(col("reliability_score") < 0, lit(0))
    .when(col("reliability_score") > 1, lit(1))
    .otherwise(col("reliability_score")),
)

df_sup = df_sup.withColumn("_processed_at", current_timestamp())

df_sup.write.format("delta").mode("overwrite").saveAsTable("silver_suppliers")
final_sup = df_sup.count()
print(f"  Written: {final_sup} rows to silver_suppliers")

# ═══════════════════════════════════════════════
#  WAREHOUSES
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing warehouses...")
print("=" * 50)

df_wh_raw = spark.read.format("delta").table("bronze_warehouses")
total_wh = df_wh_raw.count()
print(f"  Rows read: {total_wh}")

# Validate current_utilization_pct between 0 and 100 (clamp)
df_wh = df_wh_raw.withColumn(
    "current_utilization_pct",
    when(col("current_utilization_pct") < 0, lit(0))
    .when(col("current_utilization_pct") > 100, lit(100))
    .otherwise(col("current_utilization_pct")),
)

# Trim / standardise strings
df_wh = (
    df_wh
    .withColumn("warehouse_name", trim(col("warehouse_name")))
    .withColumn("city", initcap(lower(trim(col("city")))))
    .withColumn("state", initcap(lower(trim(col("state")))))
    .withColumn("country", initcap(lower(trim(col("country")))))
    .withColumn("manager_name", trim(col("manager_name")))
)

df_wh = df_wh.withColumn("_processed_at", current_timestamp())

df_wh.write.format("delta").mode("overwrite").saveAsTable("silver_warehouses")
final_wh = df_wh.count()
print(f"  Written: {final_wh} rows to silver_warehouses")

# ═══════════════════════════════════════════════
#  SHIPMENTS
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing shipments...")
print("=" * 50)

df_ship_raw = spark.read.format("delta").table("bronze_shipments")
total_ship = df_ship_raw.count()
print(f"  Rows read: {total_ship}")

# Standardise transport_mode and status
df_ship = (
    df_ship_raw
    .withColumn("transport_mode", initcap(lower(trim(col("transport_mode")))))
    .withColumn("status", initcap(lower(trim(col("status")))))
)

# Calculate delivery_delay_days where actual_arrival is not null
df_ship = df_ship.withColumn(
    "delivery_delay_days",
    when(
        col("actual_arrival").isNotNull(),
        datediff(col("actual_arrival"), col("expected_arrival")),
    ).otherwise(lit(None)),
)

# Flags: is_late (delay > 0), is_on_time (delay <= 0)
df_ship = (
    df_ship
    .withColumn(
        "is_late",
        when(col("delivery_delay_days").isNotNull(),
             col("delivery_delay_days") > 0)
        .otherwise(lit(None).cast("boolean")),
    )
    .withColumn(
        "is_on_time",
        when(col("delivery_delay_days").isNotNull(),
             col("delivery_delay_days") <= 0)
        .otherwise(lit(None).cast("boolean")),
    )
)

df_ship = df_ship.withColumn("_processed_at", current_timestamp())

df_ship.write.format("delta").mode("overwrite").saveAsTable("silver_shipments")
final_ship = df_ship.count()
print(f"  Written: {final_ship} rows to silver_shipments")

# ═══════════════════════════════════════════════
#  INVENTORY
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing inventory...")
print("=" * 50)

df_inv_raw = spark.read.format("delta").table("bronze_inventory")
total_inv = df_inv_raw.count()
print(f"  Rows read: {total_inv}")

# Validate movement_type against allowed values
ALLOWED_MOVEMENT_TYPES = ["Receipt", "Sale", "Return", "Adjustment", "Transfer"]

df_inv = df_inv_raw.withColumn(
    "movement_type", initcap(lower(trim(col("movement_type"))))
)

# Filter out invalid movement types
df_inv = df_inv.filter(col("movement_type").isin(ALLOWED_MOVEMENT_TYPES))
inv_filtered = total_inv - df_inv.count()
print(f"  Filtered out (invalid movement_type): {inv_filtered}")

# Validate quantities and costs
df_inv = df_inv.filter(col("unit_cost") >= 0)

# Ensure on_hand_after is non-negative (clamp at 0)
df_inv = df_inv.withColumn(
    "on_hand_after",
    when(col("on_hand_after") < 0, lit(0)).otherwise(col("on_hand_after")),
)

# Ensure reorder_point is non-negative
df_inv = df_inv.withColumn(
    "reorder_point",
    when(col("reorder_point") < 0, lit(0)).otherwise(col("reorder_point")),
)

# Add is_below_reorder flag at silver level for early alerting
df_inv = df_inv.withColumn(
    "is_below_reorder",
    col("on_hand_after") < col("reorder_point"),
)

# Deduplicate by inventory_id (keep latest movement_date)
from pyspark.sql.window import Window as W

window_inv_dedup = W.partitionBy("inventory_id").orderBy(col("movement_date").desc())
df_inv = (
    df_inv.withColumn("_rn", row_number().over(window_inv_dedup))
    .filter(col("_rn") == 1)
    .drop("_rn")
)

df_inv = df_inv.withColumn("_processed_at", current_timestamp())

df_inv.write.format("delta").mode("overwrite").saveAsTable("silver_inventory")
final_inv = df_inv.count()
print(f"  Written: {final_inv} rows to silver_inventory")

# ═══════════════════════════════════════════════
#  SUPPLY RELATIONSHIPS
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing supply relationships...")
print("=" * 50)

df_rel_raw = spark.read.format("delta").table("bronze_supply_relationships")
total_rel = df_rel_raw.count()
print(f"  Rows read: {total_rel}")

# Allowed relationship types
ALLOWED_RELATIONSHIP_TYPES = [
    "supplies",
    "stocks",
    "ships_to",
    "distributes",
]

df_rel = df_rel_raw.filter(
    lower(trim(col("relationship_type"))).isin(
        [rt.lower() for rt in ALLOWED_RELATIONSHIP_TYPES]
    )
)
rel_filtered = total_rel - df_rel.count()
print(f"  Filtered out (invalid relationship_type): {rel_filtered}")

# Standardise
df_rel = (
    df_rel
    .withColumn("relationship_type", initcap(lower(trim(col("relationship_type")))))
    .withColumn("source_type", initcap(lower(trim(col("source_type")))))
    .withColumn("target_type", initcap(lower(trim(col("target_type")))))
)

df_rel = df_rel.withColumn("_processed_at", current_timestamp())

df_rel.write.format("delta").mode("overwrite").saveAsTable("silver_supply_relationships")
final_rel = df_rel.count()
print(f"  Written: {final_rel} rows to silver_supply_relationships")

# ═══════════════════════════════════════════════
#  Summary Statistics
# ═══════════════════════════════════════════════
print("\n" + "=" * 50)
print("Supply Chain Silver Transformation Summary")
print("=" * 50)
print(f"  Suppliers:            {total_sup} read → {final_sup} written")
print(f"  Warehouses:           {total_wh} read → {final_wh} written")
print(f"  Shipments:            {total_ship} read → {final_ship} written")
print(f"  Inventory:            {total_inv} read → {final_inv} written"
      f" ({inv_filtered} invalid types removed)")
print(f"  Supply Relationships: {total_rel} read → {final_rel} written"
      f" ({rel_filtered} invalid types removed)")
print("Supply chain silver transformation complete.")
