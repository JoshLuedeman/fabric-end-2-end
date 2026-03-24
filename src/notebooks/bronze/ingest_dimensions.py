# Fabric Notebook: Ingest Dimension Tables
# Reads all dimension parquet files from Files/bronze/ and creates Delta tables
# Covers: customers, products, stores, employees, suppliers, warehouses, supply_relationships

from pyspark.sql.functions import col, current_timestamp, lit

# Dimension tables to ingest: (source_file_stem, target_table_name)
DIMENSION_TABLES = [
    ("customers", "bronze_customers"),
    ("products", "bronze_products"),
    ("stores", "bronze_stores"),
    ("employees", "bronze_employees"),
    ("suppliers", "bronze_suppliers"),
    ("warehouses", "bronze_warehouses"),
    ("supply_relationships", "bronze_supply_relationships"),
]

for source_name, table_name in DIMENSION_TABLES:
    source_file = f"{source_name}.parquet"
    source_path = f"Files/bronze/{source_file}"

    print(f"Ingesting {source_name}...")
    df = spark.read.parquet(source_path)
    df = (
        df
        .withColumn("_ingested_at", current_timestamp())
        .withColumn("_source_file", lit(source_file))
    )
    df.write.format("delta").mode("overwrite").saveAsTable(table_name)
    print(f"  Ingested {df.count()} records to {table_name}")

print("Dimension bronze ingestion complete.")
