/*
 * Staging Schema & Tables
 * Microsoft Fabric Warehouse
 *
 * Mirrors gold Lakehouse table structures for ETL staging.
 * Tables are truncated and reloaded each pipeline run.
 */

-- Create the staging schema
CREATE SCHEMA staging;
GO

-- ============================================================
-- staging.stg_fact_sales
-- ============================================================
CREATE TABLE staging.stg_fact_sales (
    sale_sk             BIGINT          NOT NULL,
    date_key            INT             NOT NULL,
    customer_sk         INT             NOT NULL,
    product_sk          INT             NOT NULL,
    store_sk            INT             NOT NULL,
    transaction_id      VARCHAR(20),
    quantity            INT,
    unit_price          DECIMAL(10,2),
    discount_pct        DECIMAL(5,2),
    gross_amount        DECIMAL(12,2),
    net_amount          DECIMAL(12,2),
    tax_amount          DECIMAL(12,2),
    total_amount        DECIMAL(12,2),
    payment_method      VARCHAR(20),
    channel             VARCHAR(20)
);
GO

-- ============================================================
-- staging.stg_fact_inventory
-- ============================================================
CREATE TABLE staging.stg_fact_inventory (
    inventory_sk        BIGINT          NOT NULL,
    date_key            INT             NOT NULL,
    product_sk          INT             NOT NULL,
    store_sk            INT             NOT NULL,
    inventory_id        VARCHAR(20),
    movement_type       VARCHAR(20),
    quantity            INT,
    unit_cost           DECIMAL(10,2),
    on_hand_after       INT,
    reorder_point       INT,
    is_below_reorder    BIT
);
GO

-- ============================================================
-- staging.stg_dim_customer
-- ============================================================
CREATE TABLE staging.stg_dim_customer (
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
-- staging.stg_dim_product
-- ============================================================
CREATE TABLE staging.stg_dim_product (
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
-- staging.stg_dim_store
-- ============================================================
CREATE TABLE staging.stg_dim_store (
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
