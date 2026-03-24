-- ==========================================================================
-- Contoso Global Retail — Marketing Analytics Schema (PostgreSQL in Fabric)
--
-- The marketing team's dedicated analytical database. PostgreSQL was chosen
-- for its native JSON operators (campaign metadata, A/B test variants),
-- PostGIS support (geo-analysis of campaign reach by store location), and
-- rich extension ecosystem.
--
-- Workspace: analytics
-- Owner: Marketing Analytics Team
-- ==========================================================================

-- --------------------------------------------------------------------------
-- Extensions
-- --------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation
CREATE EXTENSION IF NOT EXISTS "postgis";     -- Geospatial analysis
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- Trigram text similarity

-- --------------------------------------------------------------------------
-- Schema
-- --------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS marketing;
COMMENT ON SCHEMA marketing IS 'Contoso marketing analytics — campaigns, A/B tests, attribution, spend';

SET search_path TO marketing, public;

-- --------------------------------------------------------------------------
-- Table: campaigns
-- Core campaign definitions with metadata stored as JSONB for flexibility.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.campaigns (
    campaign_id         UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_name       VARCHAR(200)    NOT NULL,
    campaign_type       VARCHAR(50)     NOT NULL
        CHECK (campaign_type IN ('email', 'social', 'paid_search', 'display', 'influencer', 'direct_mail', 'sms', 'push_notification')),
    channel             VARCHAR(50)     NOT NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'active', 'paused', 'completed', 'cancelled')),
    objective           VARCHAR(50)     NOT NULL
        CHECK (objective IN ('awareness', 'acquisition', 'retention', 'reactivation', 'upsell', 'cross_sell')),
    target_audience     JSONB           NOT NULL DEFAULT '{}',
    -- Example: {"segments": ["high-value-regular"], "age_range": [25, 54], "geo": ["US-TX", "US-CA"]}
    budget_usd          NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    start_date          DATE            NOT NULL,
    end_date            DATE,
    created_by          VARCHAR(100)    NOT NULL,
    metadata            JSONB           DEFAULT '{}',
    -- Flexible metadata: creative assets, UTM params, approval chain, etc.
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_campaign_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

COMMENT ON TABLE marketing.campaigns IS 'Marketing campaigns across all channels — email, social, paid search, display, etc.';
COMMENT ON COLUMN marketing.campaigns.target_audience IS 'JSONB — audience targeting: segments, demographics, geo-fencing';
COMMENT ON COLUMN marketing.campaigns.metadata IS 'JSONB — flexible metadata: creative URLs, UTM parameters, approval chain';

CREATE INDEX idx_campaigns_status ON marketing.campaigns (status);
CREATE INDEX idx_campaigns_type ON marketing.campaigns (campaign_type);
CREATE INDEX idx_campaigns_dates ON marketing.campaigns (start_date, end_date);
CREATE INDEX idx_campaigns_target_audience ON marketing.campaigns USING GIN (target_audience);

-- --------------------------------------------------------------------------
-- Table: campaign_segments
-- Many-to-many link between campaigns and customer segments.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.campaign_segments (
    campaign_id     UUID            NOT NULL REFERENCES marketing.campaigns(campaign_id) ON DELETE CASCADE,
    segment_name    VARCHAR(100)    NOT NULL,
    segment_size    INTEGER         NOT NULL DEFAULT 0,
    inclusion_type  VARCHAR(10)     NOT NULL DEFAULT 'include'
        CHECK (inclusion_type IN ('include', 'exclude')),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (campaign_id, segment_name)
);

COMMENT ON TABLE marketing.campaign_segments IS 'Customer segments targeted (or excluded) by each campaign';

-- --------------------------------------------------------------------------
-- Table: ab_tests
-- A/B and multivariate test definitions linked to campaigns.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.ab_tests (
    test_id             UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id         UUID            NOT NULL REFERENCES marketing.campaigns(campaign_id) ON DELETE CASCADE,
    test_name           VARCHAR(200)    NOT NULL,
    hypothesis          TEXT            NOT NULL,
    test_type           VARCHAR(20)     NOT NULL DEFAULT 'ab'
        CHECK (test_type IN ('ab', 'multivariate', 'bandit')),
    variants            JSONB           NOT NULL,
    -- Example: [{"id": "A", "name": "Control", "weight": 0.5}, {"id": "B", "name": "New CTA", "weight": 0.5}]
    primary_metric      VARCHAR(50)     NOT NULL,
    -- e.g., 'conversion_rate', 'click_through_rate', 'revenue_per_recipient'
    confidence_threshold NUMERIC(5, 4)  NOT NULL DEFAULT 0.9500,
    status              VARCHAR(20)     NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'running', 'concluded', 'cancelled')),
    winner_variant_id   VARCHAR(20),
    start_date          TIMESTAMPTZ,
    end_date            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE marketing.ab_tests IS 'A/B and multivariate test definitions with variant configurations';

CREATE INDEX idx_ab_tests_campaign ON marketing.ab_tests (campaign_id);
CREATE INDEX idx_ab_tests_status ON marketing.ab_tests (status);

-- --------------------------------------------------------------------------
-- Table: ab_test_results
-- Aggregated results per variant per day for statistical analysis.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.ab_test_results (
    result_id           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_id             UUID            NOT NULL REFERENCES marketing.ab_tests(test_id) ON DELETE CASCADE,
    variant_id          VARCHAR(20)     NOT NULL,
    measurement_date    DATE            NOT NULL,
    impressions         INTEGER         NOT NULL DEFAULT 0,
    clicks              INTEGER         NOT NULL DEFAULT 0,
    conversions         INTEGER         NOT NULL DEFAULT 0,
    revenue_usd         NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    bounce_rate         NUMERIC(5, 4),
    avg_time_on_page_s  NUMERIC(8, 2),
    statistical_data    JSONB           DEFAULT '{}',
    -- Example: {"p_value": 0.032, "confidence": 0.968, "lift_pct": 12.4, "sample_size": 4500}
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_ab_results_per_day UNIQUE (test_id, variant_id, measurement_date)
);

COMMENT ON TABLE marketing.ab_test_results IS 'Daily aggregated A/B test metrics per variant for statistical analysis';

CREATE INDEX idx_ab_results_test_date ON marketing.ab_test_results (test_id, measurement_date);

-- --------------------------------------------------------------------------
-- Table: email_sends
-- Individual email send records (one row per recipient per campaign).
-- --------------------------------------------------------------------------

CREATE TABLE marketing.email_sends (
    send_id             UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id         UUID            NOT NULL REFERENCES marketing.campaigns(campaign_id),
    customer_id         VARCHAR(20)     NOT NULL,
    email_address       VARCHAR(255)    NOT NULL,
    variant_id          VARCHAR(20),
    subject_line        VARCHAR(500)    NOT NULL,
    sent_at             TIMESTAMPTZ     NOT NULL,
    delivery_status     VARCHAR(20)     NOT NULL DEFAULT 'sent'
        CHECK (delivery_status IN ('sent', 'delivered', 'bounced', 'deferred', 'dropped')),
    bounce_type         VARCHAR(10),
    -- 'hard' or 'soft'
    esp_message_id      VARCHAR(200),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE marketing.email_sends IS 'Email send log — one row per recipient per campaign send';

CREATE INDEX idx_email_sends_campaign ON marketing.email_sends (campaign_id);
CREATE INDEX idx_email_sends_customer ON marketing.email_sends (customer_id);
CREATE INDEX idx_email_sends_sent_at ON marketing.email_sends (sent_at);

-- --------------------------------------------------------------------------
-- Table: email_events
-- Engagement events: opens, clicks, unsubscribes, spam reports.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.email_events (
    event_id            UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    send_id             UUID            NOT NULL REFERENCES marketing.email_sends(send_id),
    campaign_id         UUID            NOT NULL REFERENCES marketing.campaigns(campaign_id),
    customer_id         VARCHAR(20)     NOT NULL,
    event_type          VARCHAR(20)     NOT NULL
        CHECK (event_type IN ('open', 'click', 'unsubscribe', 'spam_report', 'forward')),
    event_timestamp     TIMESTAMPTZ     NOT NULL,
    link_url            TEXT,
    -- Populated for 'click' events
    user_agent          TEXT,
    ip_address          INET,
    geo_location        GEOGRAPHY(POINT, 4326),
    -- PostGIS point for geo-analysis of engagement
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE marketing.email_events IS 'Email engagement events — opens, clicks, unsubscribes, spam reports';
COMMENT ON COLUMN marketing.email_events.geo_location IS 'PostGIS POINT — approximate location of the subscriber at event time';

CREATE INDEX idx_email_events_send ON marketing.email_events (send_id);
CREATE INDEX idx_email_events_campaign ON marketing.email_events (campaign_id);
CREATE INDEX idx_email_events_type ON marketing.email_events (event_type);
CREATE INDEX idx_email_events_timestamp ON marketing.email_events (event_timestamp);
CREATE INDEX idx_email_events_geo ON marketing.email_events USING GIST (geo_location);

-- --------------------------------------------------------------------------
-- Table: attribution_touchpoints
-- Multi-touch attribution tracking for the customer purchase journey.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.attribution_touchpoints (
    touchpoint_id       UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id         VARCHAR(20)     NOT NULL,
    session_id          VARCHAR(100),
    campaign_id         UUID            REFERENCES marketing.campaigns(campaign_id),
    channel             VARCHAR(50)     NOT NULL,
    touchpoint_type     VARCHAR(30)     NOT NULL
        CHECK (touchpoint_type IN ('impression', 'click', 'visit', 'email_open', 'social_engage', 'search_click', 'direct', 'referral')),
    touchpoint_timestamp TIMESTAMPTZ    NOT NULL,
    conversion_flag     BOOLEAN         NOT NULL DEFAULT FALSE,
    conversion_value    NUMERIC(12, 2),
    order_id            VARCHAR(30),
    utm_source          VARCHAR(100),
    utm_medium          VARCHAR(100),
    utm_campaign        VARCHAR(200),
    utm_content         VARCHAR(200),
    utm_term            VARCHAR(200),
    page_url            TEXT,
    referrer_url        TEXT,
    device_type         VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE marketing.attribution_touchpoints IS 'Multi-touch attribution — every touchpoint in the customer journey toward conversion';

CREATE INDEX idx_attribution_customer ON marketing.attribution_touchpoints (customer_id);
CREATE INDEX idx_attribution_campaign ON marketing.attribution_touchpoints (campaign_id);
CREATE INDEX idx_attribution_timestamp ON marketing.attribution_touchpoints (touchpoint_timestamp);
CREATE INDEX idx_attribution_conversion ON marketing.attribution_touchpoints (conversion_flag) WHERE conversion_flag = TRUE;

-- --------------------------------------------------------------------------
-- Table: marketing_spend
-- Daily marketing spend by channel and campaign for ROI analysis.
-- --------------------------------------------------------------------------

CREATE TABLE marketing.marketing_spend (
    spend_id            UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id         UUID            REFERENCES marketing.campaigns(campaign_id),
    spend_date          DATE            NOT NULL,
    channel             VARCHAR(50)     NOT NULL,
    platform            VARCHAR(50),
    -- e.g., 'Google Ads', 'Meta Ads Manager', 'Mailchimp', 'LinkedIn'
    spend_usd           NUMERIC(12, 2)  NOT NULL,
    impressions         BIGINT          DEFAULT 0,
    clicks              INTEGER         DEFAULT 0,
    cpm_usd             NUMERIC(8, 4)   GENERATED ALWAYS AS (
        CASE WHEN impressions > 0 THEN (spend_usd / impressions) * 1000 ELSE NULL END
    ) STORED,
    cpc_usd             NUMERIC(8, 4)   GENERATED ALWAYS AS (
        CASE WHEN clicks > 0 THEN spend_usd / clicks ELSE NULL END
    ) STORED,
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_spend_per_day UNIQUE (campaign_id, spend_date, channel, platform)
);

COMMENT ON TABLE marketing.marketing_spend IS 'Daily marketing spend by channel and platform — CPM/CPC auto-calculated';

CREATE INDEX idx_spend_date ON marketing.marketing_spend (spend_date);
CREATE INDEX idx_spend_campaign ON marketing.marketing_spend (campaign_id);
CREATE INDEX idx_spend_channel ON marketing.marketing_spend (channel);
