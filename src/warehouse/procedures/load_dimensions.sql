/*
 * Stored Procedure: dbo.sp_load_dimensions
 * Microsoft Fabric Warehouse
 *
 * Loads dimension tables from the gold Lakehouse into the warehouse:
 *   1. Truncate staging tables
 *   2. INSERT INTO staging from gold_lakehouse.dbo.dim_*
 *   3. Truncate dims tables
 *   4. INSERT INTO dims from staging
 *
 * Uses TRY/CATCH for error handling and PRINT for progress tracking.
 */

CREATE PROCEDURE dbo.sp_load_dimensions
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @row_count INT;
    DECLARE @error_message NVARCHAR(4000);
    DECLARE @error_severity INT;
    DECLARE @error_state INT;

    BEGIN TRY

        -- ==========================================================
        -- STEP 1: Truncate all staging dimension tables
        -- ==========================================================
        PRINT '=== Step 1: Truncating staging dimension tables ===';

        TRUNCATE TABLE staging.stg_dim_customer;
        PRINT '  staging.stg_dim_customer truncated.';

        TRUNCATE TABLE staging.stg_dim_product;
        PRINT '  staging.stg_dim_product truncated.';

        TRUNCATE TABLE staging.stg_dim_store;
        PRINT '  staging.stg_dim_store truncated.';

        -- ==========================================================
        -- STEP 2: Load staging from gold Lakehouse
        -- ==========================================================
        PRINT '=== Step 2: Loading staging from gold Lakehouse ===';

        -- dim_customer
        INSERT INTO staging.stg_dim_customer (
            customer_sk, customer_id, first_name, last_name, email, phone,
            city, state, country, postal_code, loyalty_tier, customer_segment,
            lifetime_value, is_active, customer_age, effective_date, is_current
        )
        SELECT
            customer_sk, customer_id, first_name, last_name, email, phone,
            city, state, country, postal_code, loyalty_tier, customer_segment,
            lifetime_value, is_active, customer_age, effective_date, is_current
        FROM gold_lakehouse.dbo.dim_customer;

        SET @row_count = @@ROWCOUNT;
        PRINT '  stg_dim_customer loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- dim_product
        INSERT INTO staging.stg_dim_product (
            product_sk, product_id, product_name, category, subcategory, brand,
            unit_cost, unit_price, margin_pct, weight_kg, supplier_id,
            is_active, effective_date, is_current
        )
        SELECT
            product_sk, product_id, product_name, category, subcategory, brand,
            unit_cost, unit_price, margin_pct, weight_kg, supplier_id,
            is_active, effective_date, is_current
        FROM gold_lakehouse.dbo.dim_product;

        SET @row_count = @@ROWCOUNT;
        PRINT '  stg_dim_product loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- dim_store
        INSERT INTO staging.stg_dim_store (
            store_sk, store_id, store_name, store_type, city, state, country,
            region, latitude, longitude, square_footage, opening_date,
            effective_date, is_current
        )
        SELECT
            store_sk, store_id, store_name, store_type, city, state, country,
            region, latitude, longitude, square_footage, opening_date,
            effective_date, is_current
        FROM gold_lakehouse.dbo.dim_store;

        SET @row_count = @@ROWCOUNT;
        PRINT '  stg_dim_store loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- ==========================================================
        -- STEP 3: Truncate dims tables
        -- ==========================================================
        PRINT '=== Step 3: Truncating dims tables ===';

        TRUNCATE TABLE dims.dim_customer;
        PRINT '  dims.dim_customer truncated.';

        TRUNCATE TABLE dims.dim_product;
        PRINT '  dims.dim_product truncated.';

        TRUNCATE TABLE dims.dim_store;
        PRINT '  dims.dim_store truncated.';

        -- ==========================================================
        -- STEP 4: Load dims from staging
        -- ==========================================================
        PRINT '=== Step 4: Loading dims from staging ===';

        -- dim_customer
        INSERT INTO dims.dim_customer (
            customer_sk, customer_id, first_name, last_name, email, phone,
            city, state, country, postal_code, loyalty_tier, customer_segment,
            lifetime_value, is_active, customer_age, effective_date, is_current
        )
        SELECT
            customer_sk, customer_id, first_name, last_name, email, phone,
            city, state, country, postal_code, loyalty_tier, customer_segment,
            lifetime_value, is_active, customer_age, effective_date, is_current
        FROM staging.stg_dim_customer;

        SET @row_count = @@ROWCOUNT;
        PRINT '  dims.dim_customer loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- dim_product
        INSERT INTO dims.dim_product (
            product_sk, product_id, product_name, category, subcategory, brand,
            unit_cost, unit_price, margin_pct, weight_kg, supplier_id,
            is_active, effective_date, is_current
        )
        SELECT
            product_sk, product_id, product_name, category, subcategory, brand,
            unit_cost, unit_price, margin_pct, weight_kg, supplier_id,
            is_active, effective_date, is_current
        FROM staging.stg_dim_product;

        SET @row_count = @@ROWCOUNT;
        PRINT '  dims.dim_product loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        -- dim_store
        INSERT INTO dims.dim_store (
            store_sk, store_id, store_name, store_type, city, state, country,
            region, latitude, longitude, square_footage, opening_date,
            effective_date, is_current
        )
        SELECT
            store_sk, store_id, store_name, store_type, city, state, country,
            region, latitude, longitude, square_footage, opening_date,
            effective_date, is_current
        FROM staging.stg_dim_store;

        SET @row_count = @@ROWCOUNT;
        PRINT '  dims.dim_store loaded: ' + CAST(@row_count AS VARCHAR(20)) + ' rows.';

        PRINT '=== Dimension load completed successfully. ===';

    END TRY
    BEGIN CATCH
        SET @error_message  = ERROR_MESSAGE();
        SET @error_severity = ERROR_SEVERITY();
        SET @error_state    = ERROR_STATE();

        PRINT '!!! ERROR during dimension load !!!';
        PRINT 'Error Message:  ' + @error_message;
        PRINT 'Error Severity: ' + CAST(@error_severity AS VARCHAR(10));
        PRINT 'Error State:    ' + CAST(@error_state AS VARCHAR(10));

        -- Re-raise so callers (e.g. pipelines) see the failure
        THROW;
    END CATCH
END;
GO
