-- ===========================================================================
-- Tales & Timber ERP Schema — Tables mirrored into OneLake via Fabric Mirroring
-- Source: Azure SQL Database (simulating external ERP system)
-- Tables: Suppliers, PurchaseOrders, PurchaseOrderLines, GLJournalEntries,
--         ChartOfAccounts
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Suppliers — Master supplier list
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.Suppliers (
    supplier_id         INT             NOT NULL IDENTITY(1,1),
    supplier_code       VARCHAR(20)     NOT NULL,
    supplier_name       NVARCHAR(200)   NOT NULL,
    contact_name        NVARCHAR(100)   NULL,
    contact_email       VARCHAR(255)    NULL,
    contact_phone       VARCHAR(30)     NULL,
    address_line1       NVARCHAR(200)   NULL,
    address_line2       NVARCHAR(200)   NULL,
    city                NVARCHAR(100)   NULL,
    state_province      NVARCHAR(50)    NULL,
    postal_code         VARCHAR(20)     NULL,
    country_code        CHAR(2)         NOT NULL DEFAULT 'US',
    payment_terms_days  INT             NOT NULL DEFAULT 30,
    currency_code       CHAR(3)         NOT NULL DEFAULT 'USD',
    is_active           BIT             NOT NULL DEFAULT 1,
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    modified_at         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Suppliers PRIMARY KEY (supplier_id),
    CONSTRAINT UQ_Suppliers_Code UNIQUE (supplier_code)
);

-- ---------------------------------------------------------------------------
-- 2. PurchaseOrders — Purchase order headers
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.PurchaseOrders (
    po_id               INT             NOT NULL IDENTITY(1,1),
    po_number           VARCHAR(30)     NOT NULL,
    supplier_id         INT             NOT NULL,
    order_date          DATE            NOT NULL,
    expected_delivery   DATE            NULL,
    actual_delivery     DATE            NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'Draft',
    total_amount        DECIMAL(18,2)   NOT NULL DEFAULT 0,
    currency_code       CHAR(3)         NOT NULL DEFAULT 'USD',
    notes               NVARCHAR(500)   NULL,
    approved_by         NVARCHAR(100)   NULL,
    approved_at         DATETIME2       NULL,
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    modified_at         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_PurchaseOrders PRIMARY KEY (po_id),
    CONSTRAINT UQ_PurchaseOrders_Number UNIQUE (po_number),
    CONSTRAINT FK_PurchaseOrders_Supplier FOREIGN KEY (supplier_id)
        REFERENCES dbo.Suppliers (supplier_id),
    CONSTRAINT CK_PurchaseOrders_Status CHECK (
        status IN ('Draft', 'Submitted', 'Approved', 'Shipped', 'Received', 'Closed', 'Cancelled')
    )
);

-- ---------------------------------------------------------------------------
-- 3. PurchaseOrderLines — Purchase order line items
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.PurchaseOrderLines (
    po_line_id          INT             NOT NULL IDENTITY(1,1),
    po_id               INT             NOT NULL,
    line_number         INT             NOT NULL,
    product_sku         VARCHAR(50)     NOT NULL,
    product_name        NVARCHAR(200)   NOT NULL,
    quantity_ordered    INT             NOT NULL,
    quantity_received   INT             NOT NULL DEFAULT 0,
    unit_cost           DECIMAL(18,4)   NOT NULL,
    line_total          AS (quantity_ordered * unit_cost) PERSISTED,
    uom                 VARCHAR(20)     NOT NULL DEFAULT 'EA',
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    modified_at         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_PurchaseOrderLines PRIMARY KEY (po_line_id),
    CONSTRAINT FK_POLines_PO FOREIGN KEY (po_id)
        REFERENCES dbo.PurchaseOrders (po_id),
    CONSTRAINT UQ_POLines_LineNumber UNIQUE (po_id, line_number)
);

-- ---------------------------------------------------------------------------
-- 4. GLJournalEntries — General ledger journal entries
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.GLJournalEntries (
    journal_id          INT             NOT NULL IDENTITY(1,1),
    journal_number      VARCHAR(30)     NOT NULL,
    entry_date          DATE            NOT NULL,
    posting_date        DATE            NOT NULL,
    account_code        VARCHAR(20)     NOT NULL,
    description         NVARCHAR(500)   NOT NULL,
    debit_amount        DECIMAL(18,2)   NOT NULL DEFAULT 0,
    credit_amount       DECIMAL(18,2)   NOT NULL DEFAULT 0,
    currency_code       CHAR(3)         NOT NULL DEFAULT 'USD',
    reference_type      VARCHAR(30)     NULL,
    reference_id        VARCHAR(50)     NULL,
    posted_by           NVARCHAR(100)   NOT NULL,
    is_reversed         BIT             NOT NULL DEFAULT 0,
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    modified_at         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_GLJournalEntries PRIMARY KEY (journal_id),
    CONSTRAINT UQ_GLJournalEntries_Number UNIQUE (journal_number),
    CONSTRAINT FK_GLEntries_Account FOREIGN KEY (account_code)
        REFERENCES dbo.ChartOfAccounts (account_code)
);

-- ---------------------------------------------------------------------------
-- 5. ChartOfAccounts — Account hierarchy for financial reporting
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.ChartOfAccounts (
    account_code        VARCHAR(20)     NOT NULL,
    account_name        NVARCHAR(200)   NOT NULL,
    account_type        VARCHAR(30)     NOT NULL,
    parent_account_code VARCHAR(20)     NULL,
    hierarchy_level     INT             NOT NULL DEFAULT 1,
    is_posting_account  BIT             NOT NULL DEFAULT 1,
    normal_balance      CHAR(1)         NOT NULL DEFAULT 'D',
    is_active           BIT             NOT NULL DEFAULT 1,
    created_at          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    modified_at         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_ChartOfAccounts PRIMARY KEY (account_code),
    CONSTRAINT FK_CoA_Parent FOREIGN KEY (parent_account_code)
        REFERENCES dbo.ChartOfAccounts (account_code),
    CONSTRAINT CK_CoA_AccountType CHECK (
        account_type IN ('Asset', 'Liability', 'Equity', 'Revenue', 'Expense')
    ),
    CONSTRAINT CK_CoA_NormalBalance CHECK (normal_balance IN ('D', 'C'))
);

-- ===========================================================================
-- Indexes for common query patterns and CDC performance
-- ===========================================================================
CREATE INDEX IX_Suppliers_Active       ON dbo.Suppliers (is_active) INCLUDE (supplier_name, country_code);
CREATE INDEX IX_PO_SupplierDate        ON dbo.PurchaseOrders (supplier_id, order_date) INCLUDE (status, total_amount);
CREATE INDEX IX_PO_Status              ON dbo.PurchaseOrders (status) INCLUDE (po_number, order_date);
CREATE INDEX IX_POLines_ProductSKU     ON dbo.PurchaseOrderLines (product_sku) INCLUDE (quantity_ordered, unit_cost);
CREATE INDEX IX_GL_AccountDate         ON dbo.GLJournalEntries (account_code, posting_date) INCLUDE (debit_amount, credit_amount);
CREATE INDEX IX_GL_PostingDate         ON dbo.GLJournalEntries (posting_date) INCLUDE (account_code, debit_amount, credit_amount);
CREATE INDEX IX_CoA_ParentCode         ON dbo.ChartOfAccounts (parent_account_code) INCLUDE (account_name, account_type);

-- CDC tracking: modified_at indexes for Fabric Mirroring watermarks
CREATE INDEX IX_Suppliers_Modified     ON dbo.Suppliers (modified_at);
CREATE INDEX IX_PO_Modified            ON dbo.PurchaseOrders (modified_at);
CREATE INDEX IX_POLines_Modified       ON dbo.PurchaseOrderLines (modified_at);
CREATE INDEX IX_GL_Modified            ON dbo.GLJournalEntries (modified_at);
CREATE INDEX IX_CoA_Modified           ON dbo.ChartOfAccounts (modified_at);
