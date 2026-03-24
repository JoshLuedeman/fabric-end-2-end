/*
 * Stored Procedure: dbo.sp_load_facts
 * Microsoft Fabric Warehouse
 *
 * Loads fact tables from the gold Lakehouse into the warehouse:
 *   1. Truncate staging fact tables
 *   2. INSERT INTO staging from gold_lakehouse.dbo.fact_*
 *   3. Truncate facts tables
 *   4. INSERT INTO facts from staging
 *
 * Uses TRY/CATCH for error handling and row-count logging.
 */

CREATE PROCEDURE dbo.sp_load_facts
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @row_count INT;
    DECLARE @error_message NVARCHAR(4000);
    DECLARE @error_severity INT;
    DECLARE @error_state INT;

    BEGIN TRY

        -- ==========================================================
        -- STEP 1: Truncate staging fact tables
        -- ==========================================================
        PRINT '=== Step 1: Truncating staging fact tables ===';

        TRUNCATE TABLE staging.stg_fact_sales;
        PRINT '  staging.stg_fact_sales truncated.';

        TRUNCATE TABLE staging.stg_fact_inventory;
        PRINT '  staging.stg_fact_inventory truncated.';

        -- ==========================================================
        -- STEP 2: Load staging from gold Lakehouse
        -- ==========================================================
        PRINT '=== Step 2: Loading staging from gold Lakehouse ===';

        -- fact_sales
        INSERT INTO staging.stg_fact_sales (
            sale_sk, date_key, customer_sk, product_sk, store_sk,
            transaction_id, quantity, unit_price, discount_pct,
            gross_amount, net_amount, tax_amount, total_amount,
            payment_method, channel
        )
        SELECT
            sale_sk, date_key, customer_sk, product_sk, store_sk,
            transaction_id, quantity, unit_price, discount_pct,
            gross_amount, net_amount, tax_amount, total_amount,
            payment_method, channel
        FROM gold_lakehouse.dbo.fact_sales;

        SET @row_count = @@ROWCOUNT;
        PRINT '  stg_fact_sales loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- fact_inventory
        INSERT INTO staging.stg_fact_inventory (
            inventory_sk, date_key, product_sk, store_sk,
            inventory_id, movement_type, quantity, unit_cost,
            on_hand_after, reorder_point, is_below_reorder
        )
        SELECT
            inventory_sk, date_key, product_sk, store_sk,
            inventory_id, movement_type, quantity, unit_cost,
            on_hand_after, reorder_point, is_below_reorder
        FROM gold_lakehouse.dbo.fact_inventory;

        SET @row_count = @@ROWCOUNT;
        PRINT '  stg_fact_inventory loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- ==========================================================
        -- STEP 3: Truncate facts tables
        -- ==========================================================
        PRINT '=== Step 3: Truncating facts tables ===';

        TRUNCATE TABLE facts.fact_sales;
        PRINT '  facts.fact_sales truncated.';

        TRUNCATE TABLE facts.fact_inventory;
        PRINT '  facts.fact_inventory truncated.';

        -- ==========================================================
        -- STEP 4: Load facts from staging
        -- ==========================================================
        PRINT '=== Step 4: Loading facts from staging ===';

        -- fact_sales
        INSERT INTO facts.fact_sales (
            sale_sk, date_key, customer_sk, product_sk, store_sk,
            transaction_id, quantity, unit_price, discount_pct,
            gross_amount, net_amount, tax_amount, total_amount,
            payment_method, channel
        )
        SELECT
            sale_sk, date_key, customer_sk, product_sk, store_sk,
            transaction_id, quantity, unit_price, discount_pct,
            gross_amount, net_amount, tax_amount, total_amount,
            payment_method, channel
        FROM staging.stg_fact_sales;

        SET @row_count = @@ROWCOUNT;
        PRINT '  facts.fact_sales loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- fact_inventory
        INSERT INTO facts.fact_inventory (
            inventory_sk, date_key, product_sk, store_sk,
            inventory_id, movement_type, quantity, unit_cost,
            on_hand_after, reorder_point, is_below_reorder
        )
        SELECT
            inventory_sk, date_key, product_sk, store_sk,
            inventory_id, movement_type, quantity, unit_cost,
            on_hand_after, reorder_point, is_below_reorder
        FROM staging.stg_fact_inventory;

        SET @row_count = @@ROWCOUNT;
        PRINT '  facts.fact_inventory loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        PRINT '=== Fact load completed successfully. ===';

    END TRY
    BEGIN CATCH
        SET @error_message  = ERROR_MESSAGE();
        SET @error_severity = ERROR_SEVERITY();
        SET @error_state    = ERROR_STATE();

        PRINT '!!! ERROR during fact load !!!';
        PRINT 'Error Message:  ' + @error_message;
        PRINT 'Error Severity: ' + CAST(@error_severity AS VARCHAR(10));
        PRINT 'Error State:    ' + CAST(@error_state AS VARCHAR(10));

        -- Re-raise so callers (e.g. pipelines) see the failure
        THROW;
    END CATCH
END;
GO
