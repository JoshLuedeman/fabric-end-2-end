-- ===========================================================================
-- Contoso Operational POS Database (Fabric SQL Database)
-- Normalized OLTP schema for point-of-sale and inventory management
--
-- This is the LIVE transactional system. The analytics Lakehouse/Warehouse
-- ingests from this source via CDC and daily batch pipelines.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Customers (live customer accounts)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Customers (
    customer_id NVARCHAR(10) PRIMARY KEY,
    first_name NVARCHAR(100) NOT NULL,
    last_name NVARCHAR(100) NOT NULL,
    email NVARCHAR(255) UNIQUE,
    phone NVARCHAR(20),
    loyalty_tier NVARCHAR(20) DEFAULT 'Bronze',
    loyalty_points INT DEFAULT 0,
    preferred_store_id NVARCHAR(10),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    is_active BIT DEFAULT 1
);

-- ---------------------------------------------------------------------------
-- Products (live product catalog)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Products (
    product_id NVARCHAR(10) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    category NVARCHAR(50) NOT NULL,
    subcategory NVARCHAR(50),
    brand NVARCHAR(100),
    unit_cost DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);

-- ---------------------------------------------------------------------------
-- Stores (physical + online locations)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Stores (
    store_id NVARCHAR(10) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    store_type NVARCHAR(20) NOT NULL,
    address NVARCHAR(500),
    city NVARCHAR(100),
    state_province NVARCHAR(100),
    country NVARCHAR(50) NOT NULL,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    manager_employee_id NVARCHAR(10),
    opened_date DATE,
    is_active BIT DEFAULT 1
);

-- ---------------------------------------------------------------------------
-- Live POS Transactions (current day + recent)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Transactions (
    transaction_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    customer_id NVARCHAR(10),
    store_id NVARCHAR(10) NOT NULL,
    employee_id NVARCHAR(10),
    transaction_date DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    payment_method NVARCHAR(20),
    channel NVARCHAR(20),
    subtotal DECIMAL(12,2),
    tax_amount DECIMAL(12,2),
    discount_amount DECIMAL(12,2) DEFAULT 0,
    total_amount DECIMAL(12,2),
    loyalty_points_earned INT DEFAULT 0,
    CONSTRAINT FK_Txn_Customer FOREIGN KEY (customer_id) REFERENCES dbo.Customers(customer_id),
    CONSTRAINT FK_Txn_Store FOREIGN KEY (store_id) REFERENCES dbo.Stores(store_id)
);

CREATE INDEX IX_Transactions_Date ON dbo.Transactions(transaction_date);
CREATE INDEX IX_Transactions_Store ON dbo.Transactions(store_id, transaction_date);
CREATE INDEX IX_Transactions_Customer ON dbo.Transactions(customer_id);

-- ---------------------------------------------------------------------------
-- Transaction Line Items
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.TransactionItems (
    item_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    transaction_id UNIQUEIDENTIFIER NOT NULL,
    product_id NVARCHAR(10) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    discount_pct DECIMAL(5,2) DEFAULT 0,
    line_total DECIMAL(12,2) NOT NULL,
    CONSTRAINT FK_Item_Txn FOREIGN KEY (transaction_id) REFERENCES dbo.Transactions(transaction_id),
    CONSTRAINT FK_Item_Product FOREIGN KEY (product_id) REFERENCES dbo.Products(product_id)
);

CREATE INDEX IX_Items_Transaction ON dbo.TransactionItems(transaction_id);

-- ---------------------------------------------------------------------------
-- Live Inventory (current stock levels per store)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Inventory (
    store_id NVARCHAR(10) NOT NULL,
    product_id NVARCHAR(10) NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0,
    reorder_point INT NOT NULL,
    reorder_quantity INT NOT NULL,
    last_received_date DATETIME2,
    last_sold_date DATETIME2,
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    PRIMARY KEY (store_id, product_id),
    CONSTRAINT FK_Inv_Store FOREIGN KEY (store_id) REFERENCES dbo.Stores(store_id),
    CONSTRAINT FK_Inv_Product FOREIGN KEY (product_id) REFERENCES dbo.Products(product_id)
);

-- ---------------------------------------------------------------------------
-- Customer Interactions (CRM)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.CustomerInteractions (
    interaction_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    customer_id NVARCHAR(10) NOT NULL,
    interaction_type NVARCHAR(20) NOT NULL,
    channel NVARCHAR(20) NOT NULL,
    subject NVARCHAR(500),
    resolution_status NVARCHAR(20) DEFAULT 'pending',
    agent_employee_id NVARCHAR(10),
    satisfaction_score TINYINT,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    resolved_at DATETIME2,
    CONSTRAINT FK_Interaction_Customer FOREIGN KEY (customer_id) REFERENCES dbo.Customers(customer_id)
);

-- ---------------------------------------------------------------------------
-- Promotions (active marketing campaigns)
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Promotions (
    promo_id NVARCHAR(20) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    promo_type NVARCHAR(30) NOT NULL,
    discount_pct DECIMAL(5,2),
    min_purchase DECIMAL(10,2),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BIT DEFAULT 1,
    category_filter NVARCHAR(50),
    channel_filter NVARCHAR(20)
);

-- ---------------------------------------------------------------------------
-- CDC tracking table (simulates change data capture)
-- Records the watermark for each table so the analytics pipeline knows
-- which rows have already been extracted.
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.CDC_Watermarks (
    table_name NVARCHAR(100) PRIMARY KEY,
    last_extracted_at DATETIME2 NOT NULL,
    last_row_version BIGINT DEFAULT 0,
    rows_extracted BIGINT DEFAULT 0,
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);
