/*
 * View: reporting.vw_sales_summary
 * Microsoft Fabric Warehouse
 *
 * Aggregated sales summary joining fact_sales with date, store,
 * and product dimensions. Useful for dashboards and ad-hoc analysis.
 */

-- Ensure the reporting schema exists
CREATE SCHEMA reporting;
GO

CREATE VIEW reporting.vw_sales_summary AS
SELECT
    d.calendar_year,
    d.calendar_month_name,
    d.calendar_quarter,
    s.store_name,
    s.region,
    p.category,
    p.brand,
    SUM(f.quantity)                  AS total_quantity,
    SUM(f.gross_amount)             AS gross_revenue,
    SUM(f.net_amount)               AS net_revenue,
    SUM(f.tax_amount)               AS total_tax,
    COUNT(DISTINCT f.customer_sk)   AS unique_customers,
    COUNT(*)                        AS transaction_count
FROM facts.fact_sales f
JOIN dims.dim_date    d ON f.date_key   = d.date_key
JOIN dims.dim_store   s ON f.store_sk   = s.store_sk
JOIN dims.dim_product p ON f.product_sk = p.product_sk
GROUP BY
    d.calendar_year,
    d.calendar_month_name,
    d.calendar_quarter,
    s.store_name,
    s.region,
    p.category,
    p.brand;
GO
