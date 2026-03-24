# Databricks/Fabric notebook source
# MAGIC %md
# MAGIC # Gold Layer — dim_date
# MAGIC Builds the date dimension (full overwrite — generated range 2020–2030).

from pyspark.sql.functions import *
from pyspark.sql.window import Window

# ---------------------------------------------------------------------------
# 1. Generate date spine (2020-01-01 through 2030-12-31)
# ---------------------------------------------------------------------------
df_dates = (
    spark.range(0, 5000)
    .withColumn(
        "full_date",
        date_add(lit("2020-01-01").cast("date"), col("id").cast("int")),
    )
    .filter(col("full_date") <= lit("2030-12-31").cast("date"))
)

# ---------------------------------------------------------------------------
# 2. Build dimension
# ---------------------------------------------------------------------------

# Helper references for readability
_m = month("full_date")
_d = dayofmonth("full_date")
_dow = dayofweek("full_date")  # 1=Sun, 2=Mon, … 7=Sat

# US federal holidays
is_holiday_expr = (
    ((_m == 1) & (_d == 1))                            # New Year's Day
    | ((_m == 1) & (_dow == 2) & _d.between(15, 21))   # MLK Day (3rd Mon)
    | ((_m == 2) & (_dow == 2) & _d.between(15, 21))   # Presidents' Day (3rd Mon)
    | ((_m == 5) & (_dow == 2) & (_d >= 25))            # Memorial Day (last Mon)
    | ((_m == 7) & (_d == 4))                            # Independence Day
    | ((_m == 9) & (_dow == 2) & (_d <= 7))              # Labor Day (1st Mon)
    | ((_m == 10) & (_dow == 2) & _d.between(8, 14))    # Columbus Day (2nd Mon)
    | ((_m == 11) & (_d == 11))                          # Veterans Day
    | ((_m == 11) & (_dow == 5) & _d.between(22, 28))   # Thanksgiving (4th Thu)
    | ((_m == 12) & (_d == 25))                          # Christmas Day
)

df_dim = (
    df_dates
    .select(
        (year("full_date") * 10000 + _m * 100 + _d)
            .cast("int").alias("date_key"),
        col("full_date"),
        year("full_date").alias("year"),
        quarter("full_date").alias("quarter"),
        _m.alias("month"),
        _d.alias("day"),
        _dow.alias("day_of_week"),
        date_format("full_date", "EEEE").alias("day_name"),
        date_format("full_date", "MMMM").alias("month_name"),
        date_format("full_date", "yyyy-MM").alias("year_month"),
        concat(
            year("full_date").cast("string"),
            lit("-Q"),
            quarter("full_date").cast("string"),
        ).alias("year_quarter"),
        _dow.isin(1, 7).alias("is_weekend"),
        is_holiday_expr.alias("is_holiday"),
        when(_m >= 7, year("full_date") + 1)
            .otherwise(year("full_date"))
            .alias("fiscal_year"),
        when(_m.between(7, 9), 1)
            .when(_m.between(10, 12), 2)
            .when(_m.between(1, 3), 3)
            .otherwise(4)
            .alias("fiscal_quarter"),
        when(_m >= 7, _m - 6)
            .otherwise(_m + 6)
            .alias("fiscal_month"),
        weekofyear("full_date").alias("week_of_year"),
        dayofyear("full_date").alias("day_of_year"),
        (_d == 1).alias("is_month_start"),
        (col("full_date") == last_day(col("full_date")))
            .alias("is_month_end"),
        (_m.isin(1, 4, 7, 10) & (_d == 1))
            .alias("is_quarter_start"),
        (_m.isin(3, 6, 9, 12) & (col("full_date") == last_day(col("full_date"))))
            .alias("is_quarter_end"),
    )
)

# ---------------------------------------------------------------------------
# 3. Write to gold (overwrite)
# ---------------------------------------------------------------------------
(
    df_dim
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("dim_date")
)

print("✅ dim_date written successfully.")
