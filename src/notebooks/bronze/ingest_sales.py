# Fabric Notebook: Ingest Sales Transactions
# Reads raw sales_transactions.parquet from Files/bronze/ and creates Delta table
# Also ingests shipments and IoT telemetry data

from pyspark.sql.functions import col, current_timestamp, lit, input_file_name

# === Sales Transactions ===
print("Ingesting sales transactions...")
df_sales = spark.read.parquet("Files/bronze/sales_transactions.parquet")
df_sales = (
    df_sales
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", lit("sales_transactions.parquet"))
)
df_sales.write.format("delta").mode("overwrite").saveAsTable("bronze_sales_transactions")
print(f"Ingested {df_sales.count()} sales transactions to bronze_sales_transactions")

# === Shipments ===
print("Ingesting shipments...")
df_shipments = spark.read.parquet("Files/bronze/shipments.parquet")
df_shipments = (
    df_shipments
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", lit("shipments.parquet"))
)
df_shipments.write.format("delta").mode("overwrite").saveAsTable("bronze_shipments")
print(f"Ingested {df_shipments.count()} shipments to bronze_shipments")

# === IoT Telemetry ===
print("Ingesting IoT telemetry...")
df_iot = spark.read.parquet("Files/bronze/iot_telemetry.parquet")
df_iot = (
    df_iot
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", lit("iot_telemetry.parquet"))
)
df_iot.write.format("delta").mode("overwrite").saveAsTable("bronze_iot_telemetry")
print(f"Ingested {df_iot.count()} IoT readings to bronze_iot_telemetry")

print("Sales & operations bronze ingestion complete.")
