-- ===========================================================================
-- sp_cdc_extract — CDC extraction procedure
--
-- Called by the analytics pipeline (Fabric Data Pipeline / Notebook) to
-- pull incremental changes from the OLTP system into the bronze layer.
--
-- For each tracked table, reads rows modified since the last watermark,
-- returns them as result sets, and advances the watermark.
-- ===========================================================================

CREATE OR ALTER PROCEDURE dbo.sp_cdc_extract
    @table_name    NVARCHAR(100),     -- Which table to extract
    @batch_size    INT = 10000        -- Max rows per extraction batch
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @last_extracted_at DATETIME2;
    DECLARE @now               DATETIME2 = GETUTCDATE();
    DECLARE @rows_extracted    BIGINT    = 0;

    -- =======================================================================
    -- 1. Read the current watermark for the requested table
    -- =======================================================================
    SELECT @last_extracted_at = last_extracted_at
    FROM dbo.CDC_Watermarks
    WHERE table_name = @table_name;

    IF @last_extracted_at IS NULL
    BEGIN
        RAISERROR('No CDC watermark found for table: %s', 16, 1, @table_name);
        RETURN;
    END

    -- =======================================================================
    -- 2. Extract changed rows based on the table name
    -- =======================================================================
    IF @table_name = 'Customers'
    BEGIN
        SELECT TOP (@batch_size)
            customer_id,
            first_name,
            last_name,
            email,
            phone,
            loyalty_tier,
            loyalty_points,
            preferred_store_id,
            created_at,
            updated_at,
            is_active,
            'Customers' AS _cdc_source_table,
            @now        AS _cdc_extracted_at
        FROM dbo.Customers
        WHERE updated_at > @last_extracted_at
        ORDER BY updated_at ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'Products'
    BEGIN
        SELECT TOP (@batch_size)
            product_id,
            name,
            category,
            subcategory,
            brand,
            unit_cost,
            unit_price,
            is_active,
            created_at,
            updated_at,
            'Products' AS _cdc_source_table,
            @now       AS _cdc_extracted_at
        FROM dbo.Products
        WHERE updated_at > @last_extracted_at
        ORDER BY updated_at ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'Stores'
    BEGIN
        SELECT TOP (@batch_size)
            store_id,
            name,
            store_type,
            address,
            city,
            state_province,
            country,
            latitude,
            longitude,
            manager_employee_id,
            opened_date,
            is_active,
            'Stores' AS _cdc_source_table,
            @now     AS _cdc_extracted_at
        FROM dbo.Stores
        WHERE is_active IS NOT NULL  -- Stores lack updated_at; full extract each run
        ORDER BY store_id ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'Transactions'
    BEGIN
        SELECT TOP (@batch_size)
            transaction_id,
            customer_id,
            store_id,
            employee_id,
            transaction_date,
            payment_method,
            channel,
            subtotal,
            tax_amount,
            discount_amount,
            total_amount,
            loyalty_points_earned,
            'Transactions' AS _cdc_source_table,
            @now           AS _cdc_extracted_at
        FROM dbo.Transactions
        WHERE transaction_date > @last_extracted_at
        ORDER BY transaction_date ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'TransactionItems'
    BEGIN
        SELECT TOP (@batch_size)
            ti.item_id,
            ti.transaction_id,
            ti.product_id,
            ti.quantity,
            ti.unit_price,
            ti.discount_pct,
            ti.line_total,
            'TransactionItems' AS _cdc_source_table,
            @now               AS _cdc_extracted_at
        FROM dbo.TransactionItems ti
            INNER JOIN dbo.Transactions t ON ti.transaction_id = t.transaction_id
        WHERE t.transaction_date > @last_extracted_at
        ORDER BY t.transaction_date ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'Inventory'
    BEGIN
        SELECT TOP (@batch_size)
            store_id,
            product_id,
            quantity_on_hand,
            reorder_point,
            reorder_quantity,
            last_received_date,
            last_sold_date,
            updated_at,
            'Inventory' AS _cdc_source_table,
            @now        AS _cdc_extracted_at
        FROM dbo.Inventory
        WHERE updated_at > @last_extracted_at
        ORDER BY updated_at ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'CustomerInteractions'
    BEGIN
        SELECT TOP (@batch_size)
            interaction_id,
            customer_id,
            interaction_type,
            channel,
            subject,
            resolution_status,
            agent_employee_id,
            satisfaction_score,
            created_at,
            resolved_at,
            'CustomerInteractions' AS _cdc_source_table,
            @now                   AS _cdc_extracted_at
        FROM dbo.CustomerInteractions
        WHERE created_at > @last_extracted_at
        ORDER BY created_at ASC;

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE IF @table_name = 'Promotions'
    BEGIN
        SELECT TOP (@batch_size)
            promo_id,
            name,
            promo_type,
            discount_pct,
            min_purchase,
            start_date,
            end_date,
            is_active,
            category_filter,
            channel_filter,
            'Promotions' AS _cdc_source_table,
            @now         AS _cdc_extracted_at
        FROM dbo.Promotions;
        -- Promotions are small; always full extract

        SET @rows_extracted = @@ROWCOUNT;
    END

    ELSE
    BEGIN
        RAISERROR('Unknown table for CDC extraction: %s', 16, 1, @table_name);
        RETURN;
    END

    -- =======================================================================
    -- 3. Advance the watermark after successful extraction
    -- =======================================================================
    UPDATE dbo.CDC_Watermarks
    SET
        last_extracted_at = @now,
        rows_extracted    = rows_extracted + @rows_extracted,
        updated_at        = @now
    WHERE table_name = @table_name;

    -- Return extraction summary
    SELECT
        @table_name     AS table_name,
        @rows_extracted AS rows_extracted,
        @last_extracted_at AS previous_watermark,
        @now            AS new_watermark;
END;
GO
