/*
 * Dimension Schema & Tables
 * Microsoft Fabric Warehouse
 *
 * Contains all dimension tables for the star schema, including
 * a comprehensive date dimension with fiscal calendar support.
 */

-- Create the dims schema
CREATE SCHEMA dims;
GO

-- ============================================================
-- dims.dim_customer
-- ============================================================
CREATE TABLE dims.dim_customer (
    customer_sk         INT             NOT NULL,
    customer_id         VARCHAR(10),
    first_name          VARCHAR(100),
    last_name           VARCHAR(100),
    email               VARCHAR(200),
    phone               VARCHAR(30),
    city                VARCHAR(100),
    state               VARCHAR(50),
    country             VARCHAR(50),
    postal_code         VARCHAR(20),
    loyalty_tier        VARCHAR(20),
    customer_segment    VARCHAR(20),
    lifetime_value      DECIMAL(12,2),
    is_active           BIT,
    customer_age        INT,
    effective_date      DATE,
    is_current          BIT
);
GO

-- ============================================================
-- dims.dim_product
-- ============================================================
CREATE TABLE dims.dim_product (
    product_sk          INT             NOT NULL,
    product_id          VARCHAR(10),
    product_name        VARCHAR(200),
    category            VARCHAR(50),
    subcategory         VARCHAR(50),
    brand               VARCHAR(100),
    unit_cost           DECIMAL(10,2),
    unit_price          DECIMAL(10,2),
    margin_pct          DECIMAL(5,2),
    weight_kg           DECIMAL(8,2),
    supplier_id         VARCHAR(10),
    is_active           BIT,
    effective_date      DATE,
    is_current          BIT
);
GO

-- ============================================================
-- dims.dim_store
-- ============================================================
CREATE TABLE dims.dim_store (
    store_sk            INT             NOT NULL,
    store_id            VARCHAR(10),
    store_name          VARCHAR(200),
    store_type          VARCHAR(20),
    city                VARCHAR(100),
    state               VARCHAR(50),
    country             VARCHAR(50),
    region              VARCHAR(20),
    latitude            DECIMAL(9,6),
    longitude           DECIMAL(9,6),
    square_footage      INT,
    opening_date        DATE,
    effective_date      DATE,
    is_current          BIT
);
GO

-- ============================================================
-- dims.dim_date
-- Comprehensive date dimension with fiscal calendar.
-- Fiscal year starts July 1 (Jan-Jun = previous calendar year's fiscal year).
-- ============================================================
CREATE TABLE dims.dim_date (
    date_key            INT             NOT NULL,
    full_date           DATE,
    calendar_year       INT,
    calendar_quarter    INT,
    calendar_month      INT,
    calendar_month_name VARCHAR(20),
    calendar_week       INT,
    day_of_month        INT,
    day_of_week         INT,
    day_name            VARCHAR(20),
    is_weekend          BIT,
    is_holiday          BIT,
    fiscal_year         INT,
    fiscal_quarter      INT
);
GO

-- ============================================================
-- Procedure: dbo.sp_populate_dim_date
-- Populates dims.dim_date for years 2020 through 2030.
-- ============================================================
CREATE PROCEDURE dbo.sp_populate_dim_date
AS
BEGIN
    SET NOCOUNT ON;

    -- Clear existing date data
    TRUNCATE TABLE dims.dim_date;

    -- Recursive CTE to generate every date from 2020-01-01 to 2030-12-31
    ;WITH date_series AS (
        SELECT CAST('2020-01-01' AS DATE) AS dt
        UNION ALL
        SELECT DATEADD(DAY, 1, dt)
        FROM date_series
        WHERE dt < '2030-12-31'
    )
    INSERT INTO dims.dim_date (
        date_key,
        full_date,
        calendar_year,
        calendar_quarter,
        calendar_month,
        calendar_month_name,
        calendar_week,
        day_of_month,
        day_of_week,
        day_name,
        is_weekend,
        is_holiday,
        fiscal_year,
        fiscal_quarter
    )
    SELECT
        -- date_key in YYYYMMDD format
        CAST(FORMAT(dt, 'yyyyMMdd') AS INT)                     AS date_key,
        dt                                                       AS full_date,
        YEAR(dt)                                                 AS calendar_year,
        DATEPART(QUARTER, dt)                                    AS calendar_quarter,
        MONTH(dt)                                                AS calendar_month,
        DATENAME(MONTH, dt)                                      AS calendar_month_name,
        DATEPART(WEEK, dt)                                       AS calendar_week,
        DAY(dt)                                                  AS day_of_month,
        DATEPART(WEEKDAY, dt)                                    AS day_of_week,
        DATENAME(WEEKDAY, dt)                                    AS day_name,
        CASE WHEN DATEPART(WEEKDAY, dt) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend,
        0                                                        AS is_holiday,  -- Default; update holidays separately
        -- Fiscal year: starts July 1. Jan-Jun belongs to prior calendar year's fiscal year.
        CASE
            WHEN MONTH(dt) >= 7 THEN YEAR(dt) + 1
            ELSE YEAR(dt)
        END                                                      AS fiscal_year,
        -- Fiscal quarter: Jul-Sep = FQ1, Oct-Dec = FQ2, Jan-Mar = FQ3, Apr-Jun = FQ4
        CASE
            WHEN MONTH(dt) IN (7, 8, 9)   THEN 1
            WHEN MONTH(dt) IN (10, 11, 12) THEN 2
            WHEN MONTH(dt) IN (1, 2, 3)    THEN 3
            WHEN MONTH(dt) IN (4, 5, 6)    THEN 4
        END                                                      AS fiscal_quarter
    FROM date_series
    OPTION (MAXRECURSION 32767);

    PRINT 'dim_date populated successfully for years 2020-2030.';
END;
GO
