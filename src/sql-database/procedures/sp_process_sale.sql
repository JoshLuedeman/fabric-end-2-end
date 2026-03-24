-- ===========================================================================
-- sp_process_sale — Simulates a POS transaction
--
-- Inserts transaction header + line items, decrements inventory,
-- awards loyalty points, and updates CDC watermarks.
-- This represents what the POS terminal calls on every checkout.
-- ===========================================================================

CREATE OR ALTER PROCEDURE dbo.sp_process_sale
    @customer_id   NVARCHAR(10),
    @store_id      NVARCHAR(10),
    @employee_id   NVARCHAR(10),
    @payment_method NVARCHAR(20),
    @channel       NVARCHAR(20),
    -- Line items passed as JSON array:
    -- [{"product_id":"P-000001","quantity":2,"unit_price":29.99,"discount_pct":0}]
    @line_items    NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @transaction_id UNIQUEIDENTIFIER = NEWID();
    DECLARE @now            DATETIME2        = GETUTCDATE();
    DECLARE @subtotal       DECIMAL(12,2)    = 0;
    DECLARE @tax_rate       DECIMAL(5,4)     = 0.0825;  -- 8.25% default tax
    DECLARE @tax_amount     DECIMAL(12,2);
    DECLARE @discount_total DECIMAL(12,2)    = 0;
    DECLARE @total_amount   DECIMAL(12,2);
    DECLARE @loyalty_points INT;

    BEGIN TRANSACTION;

    -- =======================================================================
    -- 1. Parse line items from JSON and insert into TransactionItems
    -- =======================================================================
    INSERT INTO dbo.TransactionItems (
        item_id,
        transaction_id,
        product_id,
        quantity,
        unit_price,
        discount_pct,
        line_total
    )
    SELECT
        NEWID(),
        @transaction_id,
        JSON_VALUE(li.[value], '$.product_id'),
        CAST(JSON_VALUE(li.[value], '$.quantity')     AS INT),
        CAST(JSON_VALUE(li.[value], '$.unit_price')   AS DECIMAL(10,2)),
        ISNULL(CAST(JSON_VALUE(li.[value], '$.discount_pct') AS DECIMAL(5,2)), 0),
        -- line_total = quantity * unit_price * (1 - discount_pct / 100)
        CAST(JSON_VALUE(li.[value], '$.quantity') AS INT)
        * CAST(JSON_VALUE(li.[value], '$.unit_price') AS DECIMAL(10,2))
        * (1.0 - ISNULL(CAST(JSON_VALUE(li.[value], '$.discount_pct') AS DECIMAL(5,2)), 0) / 100.0)
    FROM OPENJSON(@line_items) AS li;

    -- =======================================================================
    -- 2. Calculate transaction totals
    -- =======================================================================
    SELECT
        @subtotal       = SUM(line_total),
        @discount_total = SUM(
            CAST(JSON_VALUE(li.[value], '$.quantity') AS INT)
            * CAST(JSON_VALUE(li.[value], '$.unit_price') AS DECIMAL(10,2))
            * (ISNULL(CAST(JSON_VALUE(li.[value], '$.discount_pct') AS DECIMAL(5,2)), 0) / 100.0)
        )
    FROM OPENJSON(@line_items) AS li;

    -- Recalculate subtotal from inserted items for consistency
    SELECT @subtotal = SUM(line_total)
    FROM dbo.TransactionItems
    WHERE transaction_id = @transaction_id;

    SET @tax_amount  = ROUND(@subtotal * @tax_rate, 2);
    SET @total_amount = @subtotal + @tax_amount;

    -- Loyalty: 1 point per $1 spent
    SET @loyalty_points = FLOOR(@subtotal);

    -- =======================================================================
    -- 3. Insert transaction header
    -- =======================================================================
    INSERT INTO dbo.Transactions (
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
        loyalty_points_earned
    )
    VALUES (
        @transaction_id,
        @customer_id,
        @store_id,
        @employee_id,
        @now,
        @payment_method,
        @channel,
        @subtotal,
        @tax_amount,
        @discount_total,
        @total_amount,
        @loyalty_points
    );

    -- =======================================================================
    -- 4. Update inventory — decrement quantity_on_hand per item sold
    -- =======================================================================
    UPDATE inv
    SET
        inv.quantity_on_hand = inv.quantity_on_hand - ti.quantity,
        inv.last_sold_date   = @now,
        inv.updated_at       = @now
    FROM dbo.Inventory inv
        INNER JOIN dbo.TransactionItems ti
            ON inv.product_id = ti.product_id
           AND inv.store_id   = @store_id
    WHERE ti.transaction_id = @transaction_id;

    -- =======================================================================
    -- 5. Award loyalty points to customer
    -- =======================================================================
    IF @customer_id IS NOT NULL
    BEGIN
        UPDATE dbo.Customers
        SET
            loyalty_points = loyalty_points + @loyalty_points,
            updated_at     = @now
        WHERE customer_id = @customer_id;
    END

    -- =======================================================================
    -- 6. Update CDC watermarks for affected tables
    -- =======================================================================
    UPDATE dbo.CDC_Watermarks
    SET
        last_extracted_at = @now,
        updated_at        = @now
    WHERE table_name IN ('Transactions', 'TransactionItems', 'Inventory', 'Customers');

    COMMIT TRANSACTION;

    -- Return the new transaction ID and totals
    SELECT
        @transaction_id  AS transaction_id,
        @subtotal        AS subtotal,
        @tax_amount      AS tax_amount,
        @discount_total  AS discount_amount,
        @total_amount    AS total_amount,
        @loyalty_points  AS loyalty_points_earned;
END;
GO
