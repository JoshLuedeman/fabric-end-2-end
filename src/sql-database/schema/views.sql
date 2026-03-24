-- ===========================================================================
-- Contoso Operational POS Database — Views
-- Operational views for the live OLTP system.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- vw_ActivePromotions — currently running promotions
-- Used by the POS system to apply real-time discounts at checkout.
-- ---------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_ActivePromotions
AS
SELECT
    promo_id,
    name,
    promo_type,
    discount_pct,
    min_purchase,
    start_date,
    end_date,
    category_filter,
    channel_filter
FROM dbo.Promotions
WHERE is_active = 1
  AND CAST(GETUTCDATE() AS DATE) BETWEEN start_date AND end_date;
GO

-- ---------------------------------------------------------------------------
-- vw_LowStockAlerts — products below reorder point with store info
-- Operations teams monitor this to trigger purchase orders.
-- ---------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_LowStockAlerts
AS
SELECT
    i.store_id,
    s.name          AS store_name,
    s.city,
    s.country,
    i.product_id,
    p.name          AS product_name,
    p.category,
    i.quantity_on_hand,
    i.reorder_point,
    i.reorder_quantity,
    i.last_received_date,
    i.last_sold_date,
    (i.reorder_point - i.quantity_on_hand) AS units_below_threshold
FROM dbo.Inventory i
    INNER JOIN dbo.Stores s   ON i.store_id  = s.store_id
    INNER JOIN dbo.Products p ON i.product_id = p.product_id
WHERE i.quantity_on_hand < i.reorder_point
  AND s.is_active = 1
  AND p.is_active = 1;
GO

-- ---------------------------------------------------------------------------
-- vw_DailySalesSummary — today's sales aggregated by store
-- Used for real-time dashboards and shift-end reporting.
-- ---------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_DailySalesSummary
AS
SELECT
    t.store_id,
    s.name                  AS store_name,
    s.city,
    s.country,
    CAST(t.transaction_date AS DATE) AS sale_date,
    COUNT(DISTINCT t.transaction_id) AS transaction_count,
    SUM(t.subtotal)         AS gross_sales,
    SUM(t.discount_amount)  AS total_discounts,
    SUM(t.tax_amount)       AS total_tax,
    SUM(t.total_amount)     AS net_sales,
    COUNT(DISTINCT t.customer_id) AS unique_customers,
    SUM(t.loyalty_points_earned)  AS loyalty_points_awarded
FROM dbo.Transactions t
    INNER JOIN dbo.Stores s ON t.store_id = s.store_id
WHERE CAST(t.transaction_date AS DATE) = CAST(GETUTCDATE() AS DATE)
GROUP BY
    t.store_id,
    s.name,
    s.city,
    s.country,
    CAST(t.transaction_date AS DATE);
GO

-- ---------------------------------------------------------------------------
-- vw_CustomerLifetimeValue — CLV calculation from transaction history
-- CRM and marketing teams use this to segment customers for campaigns.
-- ---------------------------------------------------------------------------
CREATE OR ALTER VIEW dbo.vw_CustomerLifetimeValue
AS
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.loyalty_tier,
    c.loyalty_points,
    COUNT(DISTINCT t.transaction_id) AS total_transactions,
    SUM(t.total_amount)              AS lifetime_spend,
    AVG(t.total_amount)              AS avg_transaction_value,
    MIN(t.transaction_date)          AS first_purchase_date,
    MAX(t.transaction_date)          AS last_purchase_date,
    DATEDIFF(DAY, MIN(t.transaction_date), MAX(t.transaction_date)) AS customer_tenure_days,
    DATEDIFF(DAY, MAX(t.transaction_date), GETUTCDATE())            AS days_since_last_purchase
FROM dbo.Customers c
    LEFT JOIN dbo.Transactions t ON c.customer_id = t.customer_id
WHERE c.is_active = 1
GROUP BY
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.loyalty_tier,
    c.loyalty_points;
GO
