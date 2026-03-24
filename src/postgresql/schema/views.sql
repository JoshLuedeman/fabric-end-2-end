-- ==========================================================================
-- Tales & Timber — Marketing Analytical Views (PostgreSQL in Fabric)
--
-- Pre-built views for the marketing team's most common analytical queries.
-- These power dashboards, reports, and ad-hoc analysis in Fabric.
-- ==========================================================================

SET search_path TO marketing, public;

-- --------------------------------------------------------------------------
-- View: campaign_performance_summary
-- One row per campaign with aggregated email, spend, and conversion metrics.
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW marketing.campaign_performance_summary AS
WITH email_stats AS (
    SELECT
        es.campaign_id,
        COUNT(DISTINCT es.send_id)                                      AS total_sends,
        COUNT(DISTINCT es.send_id) FILTER (WHERE es.delivery_status = 'delivered')
                                                                        AS delivered,
        COUNT(DISTINCT es.send_id) FILTER (WHERE es.delivery_status = 'bounced')
                                                                        AS bounced,
        COUNT(DISTINCT ee.event_id) FILTER (WHERE ee.event_type = 'open')
                                                                        AS opens,
        COUNT(DISTINCT ee.event_id) FILTER (WHERE ee.event_type = 'click')
                                                                        AS clicks,
        COUNT(DISTINCT ee.event_id) FILTER (WHERE ee.event_type = 'unsubscribe')
                                                                        AS unsubscribes
    FROM marketing.email_sends es
    LEFT JOIN marketing.email_events ee ON es.send_id = ee.send_id
    GROUP BY es.campaign_id
),
spend_stats AS (
    SELECT
        campaign_id,
        SUM(spend_usd)          AS total_spend,
        SUM(impressions)        AS total_impressions,
        SUM(clicks)             AS total_ad_clicks
    FROM marketing.marketing_spend
    GROUP BY campaign_id
),
conversion_stats AS (
    SELECT
        campaign_id,
        COUNT(*) FILTER (WHERE conversion_flag = TRUE)          AS conversions,
        SUM(conversion_value) FILTER (WHERE conversion_flag)    AS conversion_revenue
    FROM marketing.attribution_touchpoints
    GROUP BY campaign_id
)
SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.channel,
    c.status,
    c.objective,
    c.budget_usd,
    c.start_date,
    c.end_date,
    -- Email metrics
    COALESCE(em.total_sends, 0)         AS email_sends,
    COALESCE(em.delivered, 0)           AS email_delivered,
    COALESCE(em.bounced, 0)             AS email_bounced,
    COALESCE(em.opens, 0)               AS email_opens,
    COALESCE(em.clicks, 0)              AS email_clicks,
    COALESCE(em.unsubscribes, 0)        AS email_unsubscribes,
    CASE WHEN COALESCE(em.delivered, 0) > 0
         THEN ROUND(em.opens::NUMERIC / em.delivered * 100, 2)
         ELSE 0 END                     AS open_rate_pct,
    CASE WHEN COALESCE(em.opens, 0) > 0
         THEN ROUND(em.clicks::NUMERIC / em.opens * 100, 2)
         ELSE 0 END                     AS click_to_open_rate_pct,
    -- Spend metrics
    COALESCE(sp.total_spend, 0)         AS total_spend_usd,
    COALESCE(sp.total_impressions, 0)   AS total_impressions,
    COALESCE(sp.total_ad_clicks, 0)     AS total_ad_clicks,
    -- Conversion metrics
    COALESCE(cv.conversions, 0)         AS conversions,
    COALESCE(cv.conversion_revenue, 0)  AS conversion_revenue_usd,
    -- Calculated ROI
    CASE WHEN COALESCE(sp.total_spend, 0) > 0
         THEN ROUND((cv.conversion_revenue - sp.total_spend) / sp.total_spend * 100, 2)
         ELSE NULL END                  AS roi_pct,
    CASE WHEN COALESCE(cv.conversions, 0) > 0
         THEN ROUND(sp.total_spend / cv.conversions, 2)
         ELSE NULL END                  AS cost_per_acquisition_usd
FROM marketing.campaigns c
LEFT JOIN email_stats em ON c.campaign_id = em.campaign_id
LEFT JOIN spend_stats sp ON c.campaign_id = sp.campaign_id
LEFT JOIN conversion_stats cv ON c.campaign_id = cv.campaign_id;

COMMENT ON VIEW marketing.campaign_performance_summary IS
    'Unified campaign metrics: email engagement, ad spend, conversions, and ROI';

-- --------------------------------------------------------------------------
-- View: channel_attribution_report
-- Multi-touch attribution summary by channel using linear attribution model.
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW marketing.channel_attribution_report AS
WITH journey_touchpoints AS (
    -- Count total touchpoints per customer journey (conversion-linked)
    SELECT
        t.customer_id,
        t.order_id,
        t.conversion_value,
        t.channel,
        t.touchpoint_type,
        t.touchpoint_timestamp,
        COUNT(*) OVER (PARTITION BY t.customer_id, t.order_id) AS journey_length
    FROM marketing.attribution_touchpoints t
    WHERE t.order_id IS NOT NULL
),
linear_attribution AS (
    -- Linear attribution: divide conversion value equally across all touchpoints
    SELECT
        channel,
        touchpoint_type,
        COUNT(*)                                                            AS touchpoint_count,
        COUNT(DISTINCT customer_id || '|' || order_id)                     AS unique_journeys,
        SUM(conversion_value / NULLIF(journey_length, 0))                  AS attributed_revenue,
        AVG(journey_length)                                                AS avg_journey_length
    FROM journey_touchpoints
    GROUP BY channel, touchpoint_type
)
SELECT
    channel,
    touchpoint_type,
    touchpoint_count,
    unique_journeys,
    ROUND(attributed_revenue, 2)                                            AS attributed_revenue_usd,
    ROUND(avg_journey_length, 1)                                            AS avg_journey_length,
    ROUND(attributed_revenue / NULLIF(touchpoint_count, 0), 2)              AS revenue_per_touchpoint
FROM linear_attribution
ORDER BY attributed_revenue DESC;

COMMENT ON VIEW marketing.channel_attribution_report IS
    'Linear multi-touch attribution: revenue distributed equally across journey touchpoints';

-- --------------------------------------------------------------------------
-- View: customer_journey_funnel
-- Funnel analysis: impressions → clicks → visits → conversions by channel.
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW marketing.customer_journey_funnel AS
SELECT
    channel,
    COUNT(*) FILTER (WHERE touchpoint_type = 'impression')      AS impressions,
    COUNT(*) FILTER (WHERE touchpoint_type = 'click')           AS clicks,
    COUNT(*) FILTER (WHERE touchpoint_type = 'visit')           AS visits,
    COUNT(*) FILTER (WHERE touchpoint_type = 'email_open')      AS email_opens,
    COUNT(*) FILTER (WHERE touchpoint_type = 'social_engage')   AS social_engages,
    COUNT(*) FILTER (WHERE conversion_flag = TRUE)              AS conversions,
    -- Funnel conversion rates
    CASE WHEN COUNT(*) FILTER (WHERE touchpoint_type = 'impression') > 0
         THEN ROUND(
             COUNT(*) FILTER (WHERE touchpoint_type = 'click')::NUMERIC /
             COUNT(*) FILTER (WHERE touchpoint_type = 'impression') * 100, 2)
         ELSE NULL END                                          AS impression_to_click_pct,
    CASE WHEN COUNT(*) FILTER (WHERE touchpoint_type = 'click') > 0
         THEN ROUND(
             COUNT(*) FILTER (WHERE touchpoint_type = 'visit')::NUMERIC /
             COUNT(*) FILTER (WHERE touchpoint_type = 'click') * 100, 2)
         ELSE NULL END                                          AS click_to_visit_pct,
    CASE WHEN COUNT(*) FILTER (WHERE touchpoint_type = 'visit') > 0
         THEN ROUND(
             COUNT(*) FILTER (WHERE conversion_flag = TRUE)::NUMERIC /
             COUNT(*) FILTER (WHERE touchpoint_type = 'visit') * 100, 2)
         ELSE NULL END                                          AS visit_to_conversion_pct,
    SUM(conversion_value) FILTER (WHERE conversion_flag = TRUE) AS total_conversion_revenue
FROM marketing.attribution_touchpoints
GROUP BY channel
ORDER BY conversions DESC;

COMMENT ON VIEW marketing.customer_journey_funnel IS
    'Funnel analysis by channel: impression → click → visit → conversion with rates';

-- --------------------------------------------------------------------------
-- View: geo_campaign_heatmap
-- Geographic distribution of email engagement using PostGIS.
-- --------------------------------------------------------------------------

CREATE OR REPLACE VIEW marketing.geo_campaign_heatmap AS
SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    ee.event_type,
    -- Extract lat/lng from PostGIS geography
    ROUND(ST_Y(ee.geo_location::geometry)::NUMERIC, 4)         AS latitude,
    ROUND(ST_X(ee.geo_location::geometry)::NUMERIC, 4)         AS longitude,
    -- Grid bucketing for heatmap (round to 0.1 degree ≈ ~11km)
    ROUND(ST_Y(ee.geo_location::geometry)::NUMERIC, 1)         AS lat_bucket,
    ROUND(ST_X(ee.geo_location::geometry)::NUMERIC, 1)         AS lng_bucket,
    COUNT(*)                                                    AS event_count,
    COUNT(DISTINCT ee.customer_id)                              AS unique_customers
FROM marketing.email_events ee
JOIN marketing.email_sends es ON ee.send_id = es.send_id
JOIN marketing.campaigns c ON es.campaign_id = c.campaign_id
WHERE ee.geo_location IS NOT NULL
GROUP BY
    c.campaign_id, c.campaign_name, c.campaign_type, ee.event_type,
    ST_Y(ee.geo_location::geometry), ST_X(ee.geo_location::geometry),
    ROUND(ST_Y(ee.geo_location::geometry)::NUMERIC, 1),
    ROUND(ST_X(ee.geo_location::geometry)::NUMERIC, 1)
ORDER BY event_count DESC;

COMMENT ON VIEW marketing.geo_campaign_heatmap IS
    'Geographic heatmap of email engagement — uses PostGIS for lat/lng extraction and grid bucketing';
