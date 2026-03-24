/*
 * View: reporting.vw_inventory_status
 * Microsoft Fabric Warehouse
 *
 * Shows current inventory levels by product and store based on
 * the latest inventory movement record. Includes a derived
 * stock_status classification (Critical / Low / Adequate).
 *
 * Assumes reporting schema already exists (created in vw_sales_summary.sql).
 * If deploying independently, uncomment the schema line below:
 *   CREATE SCHEMA reporting;
 *   GO
 */

CREATE VIEW reporting.vw_inventory_status AS
WITH latest_inventory AS (
    SELECT
        fi.inventory_sk,
        fi.date_key,
        fi.product_sk,
        fi.store_sk,
        fi.inventory_id,
        fi.movement_type,
        fi.quantity,
        fi.unit_cost,
        fi.on_hand_after,
        fi.reorder_point,
        fi.is_below_reorder,
        ROW_NUMBER() OVER (
            PARTITION BY fi.product_sk, fi.store_sk
            ORDER BY fi.date_key DESC, fi.inventory_sk DESC
        ) AS rn
    FROM facts.fact_inventory fi
)
SELECT
    p.product_name,
    p.category,
    p.subcategory,
    p.brand,
    s.store_name,
    s.region,
    d.full_date                     AS last_movement_date,
    li.movement_type                AS last_movement_type,
    li.on_hand_after                AS current_stock,
    li.reorder_point,
    li.is_below_reorder,
    CASE
        WHEN li.on_hand_after < li.reorder_point * 0.5 THEN 'Critical'
        WHEN li.on_hand_after < li.reorder_point        THEN 'Low'
        ELSE 'Adequate'
    END                             AS stock_status
FROM latest_inventory li
JOIN dims.dim_product p ON li.product_sk = p.product_sk
JOIN dims.dim_store   s ON li.store_sk   = s.store_sk
JOIN dims.dim_date    d ON li.date_key   = d.date_key
WHERE li.rn = 1;
GO
