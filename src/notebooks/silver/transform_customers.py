# Fabric Notebook: Silver – Transform Dimension Tables
# Transforms bronze customers, products, stores, and employees into silver.

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ═══════════════════════════════════════════════
#  CUSTOMERS
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing customers...")
print("=" * 50)

df_cust_raw = spark.read.format("delta").table("bronze_customers")
total_cust = df_cust_raw.count()
print(f"  Rows read: {total_cust}")

# Trim all string columns
string_cols = [
    "first_name", "last_name", "email", "phone",
    "address", "city", "state", "country", "postal_code",
    "loyalty_tier", "customer_segment",
]
df_cust = df_cust_raw
for c in string_cols:
    df_cust = df_cust.withColumn(c, trim(col(c)))

# Standardise country: trim + title case
df_cust = df_cust.withColumn("country", initcap(lower(trim(col("country")))))

# Validate email (contains @ and .)
df_cust = df_cust.withColumn(
    "is_valid_email",
    col("email").rlike(r"^[^@]+@[^@]+\.[^@]+$"),
)

# Calculate customer age in years from date_of_birth
df_cust = df_cust.withColumn(
    "customer_age",
    floor(months_between(current_date(), col("date_of_birth")) / lit(12)).cast("int"),
)

# Deduplicate by customer_id (keep first by registration_date)
window_cust = Window.partitionBy("customer_id").orderBy("registration_date")
df_cust = (
    df_cust
    .withColumn("_row_num", row_number().over(window_cust))
    .filter(col("_row_num") == 1)
    .drop("_row_num")
)

# Add processing metadata
df_cust = df_cust.withColumn("_processed_at", current_timestamp())

df_cust.write.format("delta").mode("overwrite").saveAsTable("silver_customers")
final_cust = df_cust.count()
print(f"  Written: {final_cust} rows to silver_customers")

# ═══════════════════════════════════════════════
#  PRODUCTS
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing products...")
print("=" * 50)

df_prod_raw = spark.read.format("delta").table("bronze_products")
total_prod = df_prod_raw.count()
print(f"  Rows read: {total_prod}")

# Validate prices
df_prod = df_prod_raw.filter((col("unit_price") > 0) & (col("unit_cost") > 0))
prod_filtered = total_prod - df_prod.count()
print(f"  Filtered out (invalid price/cost): {prod_filtered}")

# Calculate margin percentage
df_prod = df_prod.withColumn(
    "margin_pct",
    round(((col("unit_price") - col("unit_cost")) / col("unit_price")) * lit(100), 2),
)

# Standardise category, subcategory to title case; trim brand
df_prod = (
    df_prod
    .withColumn("category", initcap(lower(trim(col("category")))))
    .withColumn("subcategory", initcap(lower(trim(col("subcategory")))))
    .withColumn("brand", trim(col("brand")))
)

# Deduplicate by product_id (keep first by created_date)
window_prod = Window.partitionBy("product_id").orderBy("created_date")
df_prod = (
    df_prod
    .withColumn("_row_num", row_number().over(window_prod))
    .filter(col("_row_num") == 1)
    .drop("_row_num")
)

df_prod = df_prod.withColumn("_processed_at", current_timestamp())

df_prod.write.format("delta").mode("overwrite").saveAsTable("silver_products")
final_prod = df_prod.count()
print(f"  Written: {final_prod} rows to silver_products")

# ═══════════════════════════════════════════════
#  STORES
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing stores...")
print("=" * 50)

df_store_raw = spark.read.format("delta").table("bronze_stores")
total_store = df_store_raw.count()
print(f"  Rows read: {total_store}")

# Validate geo-coordinates
df_store = df_store_raw.filter(
    (col("latitude").between(-90, 90))
    & (col("longitude").between(-180, 180))
)
store_filtered = total_store - df_store.count()
print(f"  Filtered out (invalid coordinates): {store_filtered}")

# Standardise store_type and region to title case
df_store = (
    df_store
    .withColumn("store_type", initcap(lower(trim(col("store_type")))))
    .withColumn("region", initcap(lower(trim(col("region")))))
)

df_store = df_store.withColumn("_processed_at", current_timestamp())

df_store.write.format("delta").mode("overwrite").saveAsTable("silver_stores")
final_store = df_store.count()
print(f"  Written: {final_store} rows to silver_stores")

# ═══════════════════════════════════════════════
#  EMPLOYEES
# ═══════════════════════════════════════════════
print("=" * 50)
print("Processing employees...")
print("=" * 50)

df_emp_raw = spark.read.format("delta").table("bronze_employees")
total_emp = df_emp_raw.count()
print(f"  Rows read: {total_emp}")

# Validate salary > 0
df_emp = df_emp_raw.filter(col("salary") > 0)
emp_filtered = total_emp - df_emp.count()
print(f"  Filtered out (invalid salary): {emp_filtered}")

# Clamp performance_rating between 1 and 5
df_emp = df_emp.withColumn(
    "performance_rating",
    when(col("performance_rating") < 1, lit(1))
    .when(col("performance_rating") > 5, lit(5))
    .otherwise(col("performance_rating")),
)

# Calculate tenure in years from hire_date
df_emp = df_emp.withColumn(
    "tenure_years",
    round(months_between(current_date(), col("hire_date")) / lit(12), 1),
)

df_emp = df_emp.withColumn("_processed_at", current_timestamp())

df_emp.write.format("delta").mode("overwrite").saveAsTable("silver_employees")
final_emp = df_emp.count()
print(f"  Written: {final_emp} rows to silver_employees")

# ═══════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════
print("\n" + "=" * 50)
print("Dimension Silver Transformation Summary")
print("=" * 50)
print(f"  Customers: {total_cust} read → {final_cust} written")
print(f"  Products:  {total_prod} read → {final_prod} written")
print(f"  Stores:    {total_store} read → {final_store} written")
print(f"  Employees: {total_emp} read → {final_emp} written")
print("Dimension silver transformation complete.")
