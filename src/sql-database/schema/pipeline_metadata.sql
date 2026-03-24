-- Pipeline metadata for config-driven ETL orchestration
-- Drives dynamic ingestion behavior: the ingest_metadata_driven notebook
-- reads this table to determine what to extract, from where, and how.
CREATE TABLE dbo.PipelineMetadata (
    source_name NVARCHAR(100) PRIMARY KEY,
    source_type NVARCHAR(20) NOT NULL,           -- 'table', 'file', 'api', 'stream'
    source_connection NVARCHAR(200),              -- connection reference
    source_object NVARCHAR(200) NOT NULL,         -- table name, file path, or API endpoint
    target_lakehouse NVARCHAR(100) NOT NULL,      -- bronze/silver/gold
    target_table NVARCHAR(200) NOT NULL,          -- Delta table name
    load_type NVARCHAR(20) NOT NULL DEFAULT 'incremental', -- 'full', 'incremental', 'cdc'
    watermark_column NVARCHAR(100),               -- column for incremental loads
    is_active BIT DEFAULT 1,
    schedule NVARCHAR(50) DEFAULT 'daily',        -- 'hourly', 'daily', 'weekly'
    priority INT DEFAULT 100,                     -- lower = higher priority
    last_load_timestamp DATETIME2,
    last_load_rows BIGINT DEFAULT 0,
    max_rows_per_batch BIGINT DEFAULT 1000000,
    retry_count INT DEFAULT 3,
    timeout_minutes INT DEFAULT 120,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Seed with all current data sources
-- OLTP tables (CDC-based extraction via JDBC)
INSERT INTO dbo.PipelineMetadata (source_name, source_type, source_object, target_lakehouse, target_table, load_type, watermark_column, priority) VALUES
('oltp_customers',         'table', 'dbo.Customers',            'bronze', 'bronze_sqldb_customers',          'cdc',  'updated_at',       10),
('oltp_products',          'table', 'dbo.Products',             'bronze', 'bronze_sqldb_products',           'cdc',  'updated_at',       10),
('oltp_stores',            'table', 'dbo.Stores',               'bronze', 'bronze_sqldb_stores',             'cdc',  'updated_at',       10),
('oltp_transactions',      'table', 'dbo.Transactions',         'bronze', 'bronze_sqldb_transactions',       'cdc',  'transaction_date', 20),
('oltp_transaction_items', 'table', 'dbo.TransactionItems',     'bronze', 'bronze_sqldb_transaction_items',  'cdc',  NULL,               20),
('oltp_inventory',         'table', 'dbo.Inventory',            'bronze', 'bronze_sqldb_inventory',          'cdc',  'updated_at',       30),
('oltp_interactions',      'table', 'dbo.CustomerInteractions', 'bronze', 'bronze_sqldb_interactions',       'cdc',  'created_at',       30),
('oltp_promotions',        'table', 'dbo.Promotions',           'bronze', 'bronze_sqldb_promotions',         'full', NULL,               10);

-- File-based sources (Parquet from lakehouse Files/)
INSERT INTO dbo.PipelineMetadata (source_name, source_type, source_object, target_lakehouse, target_table, load_type, watermark_column, priority) VALUES
('file_customers',    'file', 'Files/bronze/customers.parquet',        'bronze', 'bronze_customers',             'full', NULL, 50),
('file_products',     'file', 'Files/bronze/products.parquet',         'bronze', 'bronze_products',              'full', NULL, 50),
('file_sales',        'file', 'Files/bronze/sales_transactions/',      'bronze', 'bronze_sales_transactions',    'full', NULL, 60),
('file_inventory',    'file', 'Files/bronze/inventory/',               'bronze', 'bronze_inventory',             'full', NULL, 60),
('file_iot',          'file', 'Files/bronze/iot_telemetry/',           'bronze', 'bronze_iot_telemetry',         'full', NULL, 70),
('file_clickstream',  'file', 'Files/bronze/web_clickstream/',         'bronze', 'bronze_web_clickstream',       'full', NULL, 70),
('file_interactions', 'file', 'Files/bronze/customer_interactions/',   'bronze', 'bronze_customer_interactions', 'full', NULL, 70);
