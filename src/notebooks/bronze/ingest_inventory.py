# Fabric Notebook: Ingest Inventory
# Reads raw inventory.parquet from Files/bronze/ and creates Delta table

from pyspark.sql.functions import col, current_timestamp, lit

# === Inventory ===
print("Ingesting inventory movements...")
df_inventory = spark.read.parquet("Files/bronze/inventory.parquet")
df_inventory = (
    df_inventory
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", lit("inventory.parquet"))
)
df_inventory.write.format("delta").mode("overwrite").saveAsTable("bronze_inventory")
print(f"Ingested {df_inventory.count()} inventory records to bronze_inventory")

print("Inventory bronze ingestion complete.")
