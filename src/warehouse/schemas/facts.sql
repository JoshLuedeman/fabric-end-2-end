/*
 * Fact Schema & Tables
 * Microsoft Fabric Warehouse
 *
 * Contains fact tables for the star schema:
 *   - fact_sales:     transactional sales data
 *   - fact_inventory: inventory movement data
 */

-- Create the facts schema
CREATE SCHEMA facts;
GO

-- ============================================================
-- facts.fact_sales
-- ============================================================
CREATE TABLE facts.fact_sales (
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
-- facts.fact_inventory
-- ============================================================
CREATE TABLE facts.fact_inventory (
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
