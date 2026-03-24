-- ===========================================================================
-- Contoso Operational POS Database — Seed Data
-- Inserts initial reference data into the OLTP tables.
--
-- ID formats match the data generators:
--   Customer: C-{n:07d}   Product: P-{n:06d}   Store: S-{n:04d}
--   Employee: E-{n:06d}   Promo:   PROMO-{n:05d}
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Stores — 10 representative locations (mix of types and geographies)
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Stores (store_id, name, store_type, address, city, state_province, country, latitude, longitude, manager_employee_id, opened_date, is_active)
VALUES
    ('S-0001', 'Contoso Flagship NYC',       'Flagship', '5th Avenue 1000',     'New York',      'New York',        'US', 40.758896, -73.985130, 'E-000001', '2019-03-15', 1),
    ('S-0002', 'Contoso Standard Chicago',   'Standard', '123 Michigan Ave',    'Chicago',       'Illinois',        'US', 41.878113, -87.629799, 'E-000002', '2020-06-01', 1),
    ('S-0003', 'Contoso Express LA',         'Express',  '456 Sunset Blvd',     'Los Angeles',   'California',      'US', 34.052235, -118.243683,'E-000003', '2021-01-10', 1),
    ('S-0004', 'Contoso Outlet Dallas',      'Outlet',   '789 Commerce St',     'Dallas',        'Texas',           'US', 32.776664, -96.796988, 'E-000004', '2020-11-20', 1),
    ('S-0005', 'Contoso Standard London',    'Standard', '10 Oxford Street',    'London',        'Greater London',  'UK', 51.507351, -0.127758,  'E-000005', '2019-08-25', 1),
    ('S-0006', 'Contoso Express Berlin',     'Express',  'Friedrichstraße 50',  'Berlin',        'Berlin',          'DE', 52.520007, 13.404954,  'E-000006', '2021-04-12', 1),
    ('S-0007', 'Contoso Standard Tokyo',     'Standard', '1-1 Shibuya',         'Tokyo',         'Tokyo',           'JP', 35.689487, 139.691711, 'E-000007', '2020-02-28', 1),
    ('S-0008', 'Contoso Flagship Sydney',    'Flagship', '200 George St',       'Sydney',        'New South Wales', 'AU',-33.868820, 151.209290, 'E-000008', '2019-12-01', 1),
    ('S-0009', 'Contoso Express Miami',      'Express',  '321 Ocean Drive',     'Miami',         'Florida',         'US', 25.761680, -80.191790, 'E-000009', '2022-03-15', 1),
    ('S-0010', 'Contoso Online',             'Online',   NULL,                  NULL,            NULL,              'US', NULL,       NULL,       'E-000010', '2018-01-01', 1);

-- ---------------------------------------------------------------------------
-- Products — 20 representative products across categories
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Products (product_id, name, category, subcategory, brand, unit_cost, unit_price, is_active)
VALUES
    ('P-000001', 'TechNova Pro Laptop 15"',      'Electronics',      'Laptops',          'TechNova',    650.00, 999.99, 1),
    ('P-000002', 'VoltEdge Wireless Earbuds',     'Electronics',      'Audio',            'VoltEdge',     25.00,  59.99, 1),
    ('P-000003', 'PixelPro 4K Monitor 27"',       'Electronics',      'Monitors',         'PixelPro',    280.00, 449.99, 1),
    ('P-000004', 'CoreWave Smart Watch X2',        'Electronics',      'Wearables',        'CoreWave',    120.00, 249.99, 1),
    ('P-000005', 'NeoSync USB-C Hub 7-in-1',      'Electronics',      'Accessories',      'NeoSync',      18.00,  39.99, 1),
    ('P-000006', 'UrbanThread Denim Jacket',       'Clothing',         'Outerwear',        'UrbanThread',  35.00,  89.99, 1),
    ('P-000007', 'ClassicFit Cotton Polo',         'Clothing',         'Tops',             'ClassicFit',   12.00,  34.99, 1),
    ('P-000008', 'StridePro Running Shoes',        'Sports',           'Footwear',         'StridePro',    45.00, 119.99, 1),
    ('P-000009', 'FlexCore Yoga Mat Premium',      'Sports',           'Equipment',        'FlexCore',      8.00,  29.99, 1),
    ('P-000010', 'GreenLeaf Organic Coffee 1kg',   'Food & Beverage',  'Coffee & Tea',     'GreenLeaf',     7.50,  18.99, 1),
    ('P-000011', 'PureGlow Vitamin C Serum',       'Health & Beauty',  'Skincare',         'PureGlow',     10.00,  34.99, 1),
    ('P-000012', 'HomeNest Smart Thermostat',      'Home & Garden',    'Smart Home',       'HomeNest',     55.00, 129.99, 1),
    ('P-000013', 'LumiCraft Table Lamp',           'Home & Garden',    'Lighting',         'LumiCraft',    15.00,  44.99, 1),
    ('P-000014', 'KidsBuild STEM Robot Kit',       'Toys',             'Educational',      'KidsBuild',    22.00,  54.99, 1),
    ('P-000015', 'PageTurner Mystery Thriller',    'Books',            'Fiction',          'PageTurner',    3.00,  14.99, 1),
    ('P-000016', 'AutoShine Ceramic Coating',      'Automotive',       'Car Care',         'AutoShine',    18.00,  44.99, 1),
    ('P-000017', 'DeskPro Ergonomic Chair',        'Office',           'Furniture',        'DeskPro',     150.00, 349.99, 1),
    ('P-000018', 'QuickPrint Wireless Printer',    'Office',           'Printers',         'QuickPrint',   85.00, 179.99, 1),
    ('P-000019', 'FreshBrew Portable Blender',     'Food & Beverage',  'Appliances',       'FreshBrew',    12.00,  29.99, 1),
    ('P-000020', 'TrailMaster Hiking Backpack',    'Sports',           'Bags',             'TrailMaster',  30.00,  79.99, 1);

-- ---------------------------------------------------------------------------
-- Customers — 15 representative customers across loyalty tiers
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Customers (customer_id, first_name, last_name, email, phone, loyalty_tier, loyalty_points, preferred_store_id, is_active)
VALUES
    ('C-0000001', 'Emma',     'Johnson',  'emma.johnson1@contoso.com',     '+1-212-555-0101', 'Platinum', 15200, 'S-0001', 1),
    ('C-0000002', 'Liam',     'Williams', 'liam.williams2@contoso.com',    '+1-312-555-0102', 'Gold',      8750, 'S-0002', 1),
    ('C-0000003', 'Olivia',   'Brown',    'olivia.brown3@contoso.com',     '+1-213-555-0103', 'Gold',      6200, 'S-0003', 1),
    ('C-0000004', 'Noah',     'Jones',    'noah.jones4@contoso.com',       '+1-214-555-0104', 'Silver',    3100, 'S-0004', 1),
    ('C-0000005', 'Sophie',   'Taylor',   'sophie.taylor5@contoso.com',    '+44-20-5555-0105','Silver',    2800, 'S-0005', 1),
    ('C-0000006', 'Lukas',    'Müller',   'lukas.mueller6@contoso.com',    '+49-30-5555-0106','Silver',    2400, 'S-0006', 1),
    ('C-0000007', 'Yuki',     'Tanaka',   'yuki.tanaka7@contoso.com',     '+81-3-5555-0107', 'Gold',      7100, 'S-0007', 1),
    ('C-0000008', 'James',    'Wilson',   'james.wilson8@contoso.com',     '+61-2-5555-0108', 'Platinum', 12800, 'S-0008', 1),
    ('C-0000009', 'Isabella', 'Garcia',   'isabella.garcia9@contoso.com',  '+1-305-555-0109', 'Bronze',     450, 'S-0009', 1),
    ('C-0000010', 'Ethan',    'Martinez', 'ethan.martinez10@contoso.com',  '+1-555-555-0110', 'Bronze',     200, 'S-0010', 1),
    ('C-0000011', 'Ava',      'Anderson', 'ava.anderson11@contoso.com',    '+1-415-555-0111', 'Bronze',     100, 'S-0001', 1),
    ('C-0000012', 'William',  'Thomas',   'william.thomas12@contoso.com',  '+1-713-555-0112', 'Silver',    1900, 'S-0004', 1),
    ('C-0000013', 'Mia',      'Jackson',  'mia.jackson13@contoso.com',     '+44-20-5555-0113','Bronze',     350, 'S-0005', 1),
    ('C-0000014', 'Alexander','White',    'alexander.white14@contoso.com', '+1-617-555-0114', 'Gold',      5600, 'S-0002', 1),
    ('C-0000015', 'Charlotte','Harris',   'charlotte.harris15@contoso.com','+61-3-5555-0115', 'Bronze',      75, 'S-0008', 1);

-- ---------------------------------------------------------------------------
-- Inventory — stock levels for seed products at seed stores
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Inventory (store_id, product_id, quantity_on_hand, reorder_point, reorder_quantity, last_received_date)
VALUES
    -- Store S-0001 (Flagship NYC) — carries high-demand items
    ('S-0001', 'P-000001', 45,  20, 50, '2025-01-10'),
    ('S-0001', 'P-000002', 120, 30, 100,'2025-01-12'),
    ('S-0001', 'P-000004', 60,  15, 40, '2025-01-08'),
    ('S-0001', 'P-000006', 80,  25, 60, '2025-01-11'),
    ('S-0001', 'P-000008', 35,  10, 30, '2025-01-09'),
    ('S-0001', 'P-000010', 200, 50, 150,'2025-01-13'),
    -- Store S-0002 (Standard Chicago)
    ('S-0002', 'P-000001', 30,  15, 40, '2025-01-10'),
    ('S-0002', 'P-000003', 20,  10, 25, '2025-01-07'),
    ('S-0002', 'P-000007', 90,  30, 80, '2025-01-12'),
    ('S-0002', 'P-000012', 15,   5, 20, '2025-01-06'),
    ('S-0002', 'P-000017', 8,    3, 10, '2025-01-05'),
    -- Store S-0005 (Standard London)
    ('S-0005', 'P-000002', 85,  25, 70, '2025-01-11'),
    ('S-0005', 'P-000005', 150, 40, 100,'2025-01-13'),
    ('S-0005', 'P-000011', 60,  20, 50, '2025-01-10'),
    ('S-0005', 'P-000015', 200, 50, 150,'2025-01-14'),
    -- Store S-0007 (Standard Tokyo)
    ('S-0007', 'P-000001', 25,  10, 30, '2025-01-09'),
    ('S-0007', 'P-000004', 40,  15, 35, '2025-01-08'),
    ('S-0007', 'P-000009', 70,  20, 60, '2025-01-12'),
    ('S-0007', 'P-000014', 55,  15, 40, '2025-01-10'),
    -- Store S-0010 (Online) — high stock across many products
    ('S-0010', 'P-000001', 500, 100, 300,'2025-01-14'),
    ('S-0010', 'P-000002', 800, 200, 500,'2025-01-14'),
    ('S-0010', 'P-000003', 300, 75,  200,'2025-01-14'),
    ('S-0010', 'P-000008', 400, 100, 250,'2025-01-14'),
    ('S-0010', 'P-000010', 1000,250, 600,'2025-01-14'),
    ('S-0010', 'P-000017', 150, 30,  80, '2025-01-14');

-- ---------------------------------------------------------------------------
-- Promotions — 5 sample campaigns
-- ---------------------------------------------------------------------------
INSERT INTO dbo.Promotions (promo_id, name, promo_type, discount_pct, min_purchase, start_date, end_date, is_active, category_filter, channel_filter)
VALUES
    ('PROMO-00001', 'New Year Electronics Sale',    'percentage',  15.00,  50.00, '2025-01-01', '2025-01-31', 1, 'Electronics',     NULL),
    ('PROMO-00002', 'Valentine''s Day Special',     'percentage',  10.00,  25.00, '2025-02-01', '2025-02-14', 1, NULL,              NULL),
    ('PROMO-00003', 'Spring Clothing Clearance',    'percentage',  25.00,   0.00, '2025-03-15', '2025-04-15', 1, 'Clothing',        NULL),
    ('PROMO-00004', 'Online Exclusive — Free Ship', 'flat_amount',  0.00,  75.00, '2025-01-01', '2025-12-31', 1, NULL,              'Online'),
    ('PROMO-00005', 'Loyalty Double Points Week',   'points_mult',  0.00,   0.00, '2025-06-01', '2025-06-07', 0, NULL,              NULL);

-- ---------------------------------------------------------------------------
-- CDC Watermarks — initialize tracking for all tables
-- ---------------------------------------------------------------------------
INSERT INTO dbo.CDC_Watermarks (table_name, last_extracted_at, last_row_version, rows_extracted)
VALUES
    ('Customers',            '2025-01-01T00:00:00', 0, 0),
    ('Products',             '2025-01-01T00:00:00', 0, 0),
    ('Stores',               '2025-01-01T00:00:00', 0, 0),
    ('Transactions',         '2025-01-01T00:00:00', 0, 0),
    ('TransactionItems',     '2025-01-01T00:00:00', 0, 0),
    ('Inventory',            '2025-01-01T00:00:00', 0, 0),
    ('CustomerInteractions', '2025-01-01T00:00:00', 0, 0),
    ('Promotions',           '2025-01-01T00:00:00', 0, 0);
