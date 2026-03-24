-- ==========================================================================
-- Contoso Global Retail — Marketing Campaign Seed Data (PostgreSQL)
--
-- 15 campaigns across email, social, paid search, display, and SMS channels
-- representing a typical quarter of Contoso's marketing activity.
-- ==========================================================================

SET search_path TO marketing, public;

-- --------------------------------------------------------------------------
-- Seed: campaigns
-- --------------------------------------------------------------------------

INSERT INTO marketing.campaigns
    (campaign_id, campaign_name, campaign_type, channel, status, objective, target_audience, budget_usd, start_date, end_date, created_by, metadata)
VALUES
    -- Email campaigns
    ('a1b2c3d4-0001-4000-8000-000000000001', 'Summer Collection Early Access', 'email', 'email', 'completed', 'retention',
     '{"segments": ["high-value-regular", "top-spender"], "loyalty_tiers": ["Gold", "Platinum"]}',
     15000.00, '2025-05-15', '2025-05-25', 'marketing-team',
     '{"subject_lines": ["Your exclusive early access is here ☀️", "Summer styles — see them first"], "template_id": "TPL-SUMMER-2025"}'),

    ('a1b2c3d4-0002-4000-8000-000000000002', 'Win-Back Dormant Customers Q2', 'email', 'email', 'active', 'reactivation',
     '{"segments": ["dormant-90d", "dormant-180d"], "exclude_segments": ["unsubscribed"]}',
     8000.00, '2025-06-01', '2025-06-30', 'marketing-team',
     '{"discount_code": "COMEBACK20", "discount_pct": 20, "template_id": "TPL-WINBACK-Q2"}'),

    ('a1b2c3d4-0003-4000-8000-000000000003', 'Weekly Newsletter — June W1', 'email', 'email', 'completed', 'retention',
     '{"segments": ["newsletter-subscribers"]}',
     2000.00, '2025-06-02', '2025-06-02', 'content-team',
     '{"subject_line": "This week at Contoso: New arrivals + Recipe of the Week", "template_id": "TPL-NEWSLETTER"}'),

    ('a1b2c3d4-0004-4000-8000-000000000004', 'Loyalty Points Double Weekend', 'email', 'email', 'scheduled', 'upsell',
     '{"segments": ["all-loyalty-members"], "loyalty_tiers": ["Silver", "Gold", "Platinum"]}',
     5000.00, '2025-06-14', '2025-06-16', 'loyalty-team',
     '{"multiplier": 2, "template_id": "TPL-LOYALTY-DOUBLE"}'),

    -- Social media campaigns
    ('a1b2c3d4-0005-4000-8000-000000000005', 'Instagram Summer Style Challenge', 'social', 'instagram', 'active', 'awareness',
     '{"demographics": {"age_range": [18, 34]}, "interests": ["fashion", "lifestyle", "sustainability"]}',
     25000.00, '2025-06-01', '2025-08-31', 'social-team',
     '{"hashtag": "#ContosoSummerStyle", "influencer_handles": ["@stylebycontoso", "@sustainwear"], "platform": "Instagram"}'),

    ('a1b2c3d4-0006-4000-8000-000000000006', 'Facebook Retargeting — Cart Abandoners', 'social', 'facebook', 'active', 'acquisition',
     '{"segments": ["cart-abandoners-7d"], "demographics": {"age_range": [25, 54]}}',
     12000.00, '2025-06-01', '2025-06-30', 'performance-team',
     '{"pixel_id": "PX-CONTOSO-001", "lookalike_pct": 2, "platform": "Meta Ads Manager"}'),

    ('a1b2c3d4-0007-4000-8000-000000000007', 'TikTok Back-to-School Teaser', 'social', 'tiktok', 'draft', 'awareness',
     '{"demographics": {"age_range": [16, 24]}, "interests": ["back-to-school", "student-life"]}',
     18000.00, '2025-07-15', '2025-08-20', 'social-team',
     '{"hashtag": "#ContosoBTS", "content_type": "short_video", "platform": "TikTok Ads"}'),

    -- Paid search campaigns
    ('a1b2c3d4-0008-4000-8000-000000000008', 'Google Ads — Brand Terms', 'paid_search', 'google', 'active', 'awareness',
     '{"keywords": ["contoso", "contoso store", "contoso online", "contoso near me"]}',
     10000.00, '2025-01-01', '2025-12-31', 'performance-team',
     '{"platform": "Google Ads", "match_type": "exact", "bid_strategy": "target_impression_share"}'),

    ('a1b2c3d4-0009-4000-8000-000000000009', 'Google Ads — Summer Apparel', 'paid_search', 'google', 'active', 'acquisition',
     '{"keywords": ["summer dresses", "linen shirts", "outdoor clothing"], "geo": ["US"]}',
     20000.00, '2025-05-20', '2025-07-31', 'performance-team',
     '{"platform": "Google Ads", "match_type": "broad", "bid_strategy": "maximize_conversions", "target_roas": 4.0}'),

    ('a1b2c3d4-0010-4000-8000-000000000010', 'Bing Ads — Electronics', 'paid_search', 'bing', 'active', 'acquisition',
     '{"keywords": ["smart home hub", "wireless speakers", "laptop bags"], "geo": ["US", "CA"]}',
     8000.00, '2025-06-01', '2025-07-31', 'performance-team',
     '{"platform": "Microsoft Advertising", "match_type": "phrase", "bid_strategy": "enhanced_cpc"}'),

    -- Display campaigns
    ('a1b2c3d4-0011-4000-8000-000000000011', 'Programmatic Display — Health & Wellness', 'display', 'programmatic', 'active', 'awareness',
     '{"interests": ["health", "fitness", "organic-food"], "demographics": {"age_range": [25, 54]}}',
     15000.00, '2025-06-01', '2025-06-30', 'performance-team',
     '{"dsp": "The Trade Desk", "creative_sizes": ["300x250", "728x90", "160x600"], "frequency_cap": 5}'),

    ('a1b2c3d4-0012-4000-8000-000000000012', 'GDN Remarketing — Product Viewers', 'display', 'google_display', 'active', 'retention',
     '{"segments": ["product-viewers-14d"], "exclude_segments": ["recent-purchasers-7d"]}',
     9000.00, '2025-06-01', '2025-06-30', 'performance-team',
     '{"platform": "Google Display Network", "dynamic_creative": true, "bid_strategy": "target_cpa", "target_cpa_usd": 12.00}'),

    -- SMS campaigns
    ('a1b2c3d4-0013-4000-8000-000000000013', 'Flash Sale Alert — 48hr Electronics', 'sms', 'sms', 'completed', 'upsell',
     '{"segments": ["sms-opt-in", "tech-enthusiast"], "loyalty_tiers": ["Gold", "Platinum"]}',
     3000.00, '2025-05-24', '2025-05-26', 'promotions-team',
     '{"message_template": "⚡ 48HR FLASH SALE: Up to 40% off electronics! Shop now: contoso.com/flash", "short_url": "ctso.co/flash48"}'),

    -- Influencer campaign
    ('a1b2c3d4-0014-4000-8000-000000000014', 'Sustainable Living Influencer Series', 'influencer', 'multi-channel', 'active', 'awareness',
     '{"interests": ["sustainability", "eco-friendly", "conscious-consumer"], "demographics": {"age_range": [22, 45]}}',
     35000.00, '2025-06-01', '2025-08-31', 'brand-team',
     '{"influencers": [{"handle": "@ecojennifer", "platform": "Instagram", "followers": 280000}, {"handle": "@greenlifemax", "platform": "YouTube", "followers": 520000}], "deliverables": ["3 IG posts", "1 YT video", "5 stories"]}'),

    -- Direct mail
    ('a1b2c3d4-0015-4000-8000-000000000015', 'Premium Catalog — Fall Preview', 'direct_mail', 'postal', 'draft', 'retention',
     '{"segments": ["top-spender", "high-value-regular"], "loyalty_tiers": ["Platinum"]}',
     45000.00, '2025-08-01', '2025-08-15', 'brand-team',
     '{"print_vendor": "PrintCo Inc", "catalog_pages": 48, "finish": "matte", "estimated_recipients": 15000}');

-- --------------------------------------------------------------------------
-- Seed: campaign_segments
-- --------------------------------------------------------------------------

INSERT INTO marketing.campaign_segments (campaign_id, segment_name, segment_size, inclusion_type) VALUES
    ('a1b2c3d4-0001-4000-8000-000000000001', 'high-value-regular', 42000, 'include'),
    ('a1b2c3d4-0001-4000-8000-000000000001', 'top-spender', 8500, 'include'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'dormant-90d', 125000, 'include'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'dormant-180d', 87000, 'include'),
    ('a1b2c3d4-0002-4000-8000-000000000002', 'unsubscribed', 34000, 'exclude'),
    ('a1b2c3d4-0005-4000-8000-000000000005', 'gen-z', 180000, 'include'),
    ('a1b2c3d4-0005-4000-8000-000000000005', 'mobile-only', 95000, 'include'),
    ('a1b2c3d4-0006-4000-8000-000000000006', 'cart-abandoners-7d', 23000, 'include'),
    ('a1b2c3d4-0013-4000-8000-000000000013', 'sms-opt-in', 67000, 'include'),
    ('a1b2c3d4-0013-4000-8000-000000000013', 'tech-enthusiast', 31000, 'include'),
    ('a1b2c3d4-0015-4000-8000-000000000015', 'top-spender', 8500, 'include'),
    ('a1b2c3d4-0015-4000-8000-000000000015', 'high-value-regular', 42000, 'include');

-- --------------------------------------------------------------------------
-- Seed: ab_tests (linked to email campaigns)
-- --------------------------------------------------------------------------

INSERT INTO marketing.ab_tests
    (test_id, campaign_id, test_name, hypothesis, test_type, variants, primary_metric, confidence_threshold, status, winner_variant_id, start_date, end_date)
VALUES
    ('b1b2c3d4-0001-4000-8000-000000000001',
     'a1b2c3d4-0001-4000-8000-000000000001',
     'Subject Line Test — Summer Early Access',
     'A subject line with emoji and urgency will increase open rates by >10% vs. plain text',
     'ab',
     '[{"id": "A", "name": "Control (plain)", "weight": 0.5, "subject": "Your exclusive early access is here"}, {"id": "B", "name": "Emoji + urgency", "weight": 0.5, "subject": "Your exclusive early access is here ☀️"}]',
     'open_rate', 0.9500, 'concluded', 'B',
     '2025-05-15 08:00:00+00', '2025-05-25 23:59:59+00'),

    ('b1b2c3d4-0002-4000-8000-000000000002',
     'a1b2c3d4-0002-4000-8000-000000000002',
     'Discount vs. Free Shipping — Win-Back',
     'Free shipping offer will produce higher reactivation rate than a 20% discount for dormant customers',
     'ab',
     '[{"id": "A", "name": "20% Discount", "weight": 0.5, "offer": "20% off your next order"}, {"id": "B", "name": "Free Shipping", "weight": 0.5, "offer": "Free shipping on any order"}]',
     'conversion_rate', 0.9500, 'running', NULL,
     '2025-06-01 08:00:00+00', NULL);

-- --------------------------------------------------------------------------
-- Seed: marketing_spend (sample daily spend for active campaigns)
-- --------------------------------------------------------------------------

INSERT INTO marketing.marketing_spend
    (campaign_id, spend_date, channel, platform, spend_usd, impressions, clicks)
VALUES
    -- Google Ads Brand Terms (daily)
    ('a1b2c3d4-0008-4000-8000-000000000008', '2025-06-01', 'paid_search', 'Google Ads', 32.50, 4200, 380),
    ('a1b2c3d4-0008-4000-8000-000000000008', '2025-06-02', 'paid_search', 'Google Ads', 28.75, 3800, 345),
    ('a1b2c3d4-0008-4000-8000-000000000008', '2025-06-03', 'paid_search', 'Google Ads', 35.20, 4500, 412),
    -- Google Ads Summer Apparel
    ('a1b2c3d4-0009-4000-8000-000000000009', '2025-06-01', 'paid_search', 'Google Ads', 285.00, 42000, 1680),
    ('a1b2c3d4-0009-4000-8000-000000000009', '2025-06-02', 'paid_search', 'Google Ads', 310.50, 46000, 1840),
    ('a1b2c3d4-0009-4000-8000-000000000009', '2025-06-03', 'paid_search', 'Google Ads', 275.80, 39000, 1560),
    -- Bing Ads Electronics
    ('a1b2c3d4-0010-4000-8000-000000000010', '2025-06-01', 'paid_search', 'Microsoft Advertising', 95.00, 12000, 480),
    ('a1b2c3d4-0010-4000-8000-000000000010', '2025-06-02', 'paid_search', 'Microsoft Advertising', 88.40, 11200, 448),
    -- Facebook Retargeting
    ('a1b2c3d4-0006-4000-8000-000000000006', '2025-06-01', 'social', 'Meta Ads Manager', 180.00, 85000, 2550),
    ('a1b2c3d4-0006-4000-8000-000000000006', '2025-06-02', 'social', 'Meta Ads Manager', 195.50, 92000, 2760),
    ('a1b2c3d4-0006-4000-8000-000000000006', '2025-06-03', 'social', 'Meta Ads Manager', 172.30, 81000, 2430),
    -- Instagram Summer Style
    ('a1b2c3d4-0005-4000-8000-000000000005', '2025-06-01', 'social', 'Instagram Ads', 120.00, 65000, 1950),
    ('a1b2c3d4-0005-4000-8000-000000000005', '2025-06-02', 'social', 'Instagram Ads', 135.00, 72000, 2160),
    -- Programmatic Display
    ('a1b2c3d4-0011-4000-8000-000000000011', '2025-06-01', 'display', 'The Trade Desk', 245.00, 180000, 540),
    ('a1b2c3d4-0011-4000-8000-000000000011', '2025-06-02', 'display', 'The Trade Desk', 260.00, 195000, 585),
    ('a1b2c3d4-0011-4000-8000-000000000011', '2025-06-03', 'display', 'The Trade Desk', 238.00, 172000, 516),
    -- GDN Remarketing
    ('a1b2c3d4-0012-4000-8000-000000000012', '2025-06-01', 'display', 'Google Display Network', 155.00, 120000, 960),
    ('a1b2c3d4-0012-4000-8000-000000000012', '2025-06-02', 'display', 'Google Display Network', 148.50, 115000, 920);
