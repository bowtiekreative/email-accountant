-- ==========================================================================
-- Email Accountant — Supabase / PostgreSQL Schema
-- Full email metadata tracking + financial pipeline
-- ==========================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. EMAIL ACCOUNTS (Gmail accounts being scanned)
CREATE TABLE email_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    label           TEXT NOT NULL UNIQUE,          -- 'personal', 'business', etc.
    email_address   TEXT NOT NULL,
    provider        TEXT DEFAULT 'gmail',           -- gmail, outlook, etc.
    credentials_ref TEXT,                           -- path to credentials.json
    token_ref       TEXT,                           -- path to token.pickle
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. RAW EMAILS — Full email metadata
CREATE TABLE emails (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Account linkage
    account_id          UUID REFERENCES email_accounts(id),
    -- Gmail-specific
    gmail_message_id    TEXT UNIQUE,                -- Gmail's unique message ID
    gmail_thread_id     TEXT,                       -- Gmail thread ID
    gmail_label_ids     TEXT[],                     -- Gmail labels
    -- Email envelope
    message_id          TEXT,                       -- Message-ID header
    in_reply_to         TEXT,                       -- In-Reply-To header  
    references_header   TEXT,                       -- References header
    -- Sender / Recipients
    from_header         TEXT NOT NULL,              -- Full From header
    from_email          TEXT NOT NULL,              -- Parsed email address
    from_name           TEXT,                       -- Parsed display name
    to_header           TEXT,                       -- Full To header
    to_emails           TEXT[],                     -- Parsed recipient addresses
    cc_header           TEXT,                       -- CC header
    cc_emails           TEXT[],                     -- Parsed CC addresses
    bcc_emails          TEXT[],                     -- Parsed BCC (if available)
    reply_to            TEXT,                       -- Reply-To header
    -- Content
    subject             TEXT,
    snippet             TEXT,                       -- Gmail snippet
    body_plain          TEXT,                       -- Plain text body
    body_html           TEXT,                       -- HTML body (if available)
    content_type        TEXT,                       -- MIME content-type
    -- Timestamps
    email_date          TIMESTAMPTZ NOT NULL,       -- Date header
    received_date       TIMESTAMPTZ,                -- Received date
    -- Delivery metadata
    return_path         TEXT,
    dkim_signature      TEXT,
    spf_status          TEXT,
    list_unsubscribe    TEXT,
    -- Processing state
    is_read             BOOLEAN DEFAULT FALSE,
    is_starred          BOOLEAN DEFAULT FALSE,
    is_important        BOOLEAN DEFAULT FALSE,
    is_spam             BOOLEAN DEFAULT FALSE,
    -- Pipeline state
    status              TEXT DEFAULT 'pending'       -- pending, downloaded, extracting, categorized, errored
                        CHECK (status IN ('pending', 'downloaded', 'extracting', 'categorized', 'ledgered', 'errored')),
    -- Timestamps
    fetched_at          TIMESTAMPTZ DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup
CREATE INDEX idx_emails_from_email ON emails(from_email);
CREATE INDEX idx_emails_subject ON emails USING gin(to_tsvector('english', subject));
CREATE INDEX idx_emails_email_date ON emails(email_date DESC);
CREATE INDEX idx_emails_gmail_thread ON emails(gmail_thread_id);
CREATE INDEX idx_emails_account_status ON emails(account_id, status);
CREATE INDEX idx_emails_date_year ON emails(EXTRACT(YEAR FROM email_date));

-- 3. EMAIL ATTACHMENTS
CREATE TABLE attachments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id        UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    filepath        TEXT,                           -- Local storage path
    mime_type       TEXT,
    size_bytes      BIGINT,
    attachment_id   TEXT,                           -- Gmail attachment ID
    content_id      TEXT,                           -- CID for inline images
    is_inline       BOOLEAN DEFAULT FALSE,
    hash_sha256     TEXT,                           -- Dedup hash
    -- Processing
    ocr_status      TEXT DEFAULT 'pending'          -- pending, processing, done, error
                    CHECK (ocr_status IN ('pending', 'processing', 'done', 'error')),
    ocr_text        TEXT,                           -- Extracted OCR text
    ocr_confidence  REAL DEFAULT 0.0,
    ocr_processed_at TIMESTAMPTZ,
    downloaded_at   TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_attachments_email ON attachments(email_id);
CREATE INDEX idx_attachments_hash ON attachments(hash_sha256);

-- 4. EXTRACTED RECEIPT / FINANCIAL DATA
CREATE TABLE extracted_receipts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id        UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    attachment_id   UUID REFERENCES attachments(id),
    
    -- Core extracted fields
    vendor_name     TEXT,
    vendor_email    TEXT,
    vendor_website  TEXT,
    amount          NUMERIC(12,2),
    currency        TEXT DEFAULT 'USD',
    transaction_date DATE,
    
    -- Line items (from OCR)
    line_items      JSONB DEFAULT '[]'::jsonb,     -- [{description, price, quantity, classification}]
    subtotal        NUMERIC(12,2),
    tax_amount      NUMERIC(12,2),
    tip_amount      NUMERIC(12,2),
    total           NUMERIC(12,2),
    
    -- Order / invoice IDs
    invoice_number  TEXT,
    order_number    TEXT,
    receipt_number  TEXT,
    transaction_id  TEXT,
    
    -- Payment info
    payment_method  TEXT,                           -- credit card, debit, cash, paypal, etc.
    card_last_four  TEXT,
    billing_address TEXT,
    shipping_address TEXT,
    
    -- Merchant info
    merchant_category TEXT,
    merchant_phone   TEXT,
    merchant_address TEXT,
    
    -- Extraction confidence
    extraction_method TEXT DEFAULT 'ocr',           -- ocr, pdf_text, email_body, llm
    confidence_score  REAL DEFAULT 0.0,
    raw_text          TEXT,                         -- Original OCR/text output
    
    -- Flags
    needs_review    BOOLEAN DEFAULT FALSE,
    review_notes    TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_receipts_email ON extracted_receipts(email_id);
CREATE INDEX idx_receipts_vendor ON extracted_receipts(vendor_name);
CREATE INDEX idx_receipts_date ON extracted_receipts(transaction_date);
CREATE INDEX idx_receipts_confidence ON extracted_receipts(confidence_score);

-- 5. TRANSACTIONS (Categorized ledger entries)
CREATE TABLE transactions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id            UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    receipt_id          UUID REFERENCES extracted_receipts(id),
    account_id          UUID REFERENCES email_accounts(id),
    
    -- Source info (denormalized for fast querying)
    email_from          TEXT,
    email_subject       TEXT,
    email_date          TIMESTAMPTZ,
    
    -- Merchant / Vendor
    merchant_name       TEXT,
    merchant_email      TEXT,
    merchant_category   TEXT,
    
    -- Financial
    amount              NUMERIC(12,2) NOT NULL,
    currency            TEXT DEFAULT 'USD',
    transaction_date    DATE,
    description         TEXT,
    line_items          JSONB DEFAULT '[]'::jsonb,
    
    -- CLASSIFICATION
    domain              TEXT CHECK (domain IN ('personal', 'business', 'unknown')) DEFAULT 'unknown',
    transaction_type    TEXT CHECK (transaction_type IN ('income', 'expense', 'transfer', 'unknown')) DEFAULT 'unknown',
    category            TEXT,
    subcategory         TEXT,
    tax_category        TEXT,                       -- IRS Schedule C line
    classification_confidence NUMERIC(4,3) DEFAULT 0.0,
    classification_method TEXT DEFAULT 'rule',       -- rule, llm, manual
    
    -- Tax / Deduction
    is_deductible       BOOLEAN DEFAULT FALSE,
    deduction_rate      NUMERIC(3,2) DEFAULT 0.0,   -- 0.5 for meals, 1.0 for most
    
    -- Flags
    is_recurring        BOOLEAN DEFAULT FALSE,
    recurring_frequency TEXT,                        -- monthly, yearly, weekly
    needs_review        BOOLEAN DEFAULT FALSE,
    reviewed            BOOLEAN DEFAULT FALSE,
    flagged             BOOLEAN DEFAULT FALSE,
    flag_reason         TEXT,
    
    -- Audit trail
    attachment_path     TEXT,
    receipt_ocr_text    TEXT,
    
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Partitioning by year for performance
CREATE TABLE transactions_2025 (CHECK (EXTRACT(YEAR FROM email_date) = 2025)) INHERITS (transactions);
CREATE TABLE transactions_2026 (CHECK (EXTRACT(YEAR FROM email_date) = 2026)) INHERITS (transactions);

CREATE INDEX idx_transactions_email ON transactions(email_id);
CREATE INDEX idx_transactions_domain ON transactions(domain);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_merchant ON transactions(merchant_name);
CREATE INDEX idx_transactions_date ON transactions(email_date DESC);
CREATE INDEX idx_transactions_recurring ON transactions(is_recurring) WHERE is_recurring = TRUE;
CREATE INDEX idx_transactions_review ON transactions(needs_review) WHERE needs_review = TRUE;

-- 6. MERCHANT ALIASES (normalize vendor names)
CREATE TABLE merchant_aliases (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical   TEXT NOT NULL,
    alias       TEXT NOT NULL UNIQUE,
    category    TEXT,
    domain      TEXT CHECK (domain IN ('personal', 'business', 'both')),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_merchant_aliases_canonical ON merchant_aliases(canonical);
CREATE INDEX idx_merchant_aliases_alias ON merchant_aliases(alias);

-- 7. CATEGORIES HIERARCHY
CREATE TABLE categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL UNIQUE,
    parent_id   UUID REFERENCES categories(id),
    domain      TEXT CHECK (domain IN ('personal', 'business', 'both')),
    type        TEXT CHECK (type IN ('income', 'expense', 'both')),
    tax_relevant BOOLEAN DEFAULT FALSE,
    irs_line    TEXT,                               -- IRS Schedule C line
    description TEXT,
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 8. MONTHLY SUMMARIES (pre-computed)
CREATE TABLE monthly_summaries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID REFERENCES email_accounts(id),
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    domain          TEXT NOT NULL,
    type            TEXT NOT NULL,
    category        TEXT,
    total_amount    NUMERIC(12,2) DEFAULT 0.0,
    count           INTEGER DEFAULT 0,
    avg_amount      NUMERIC(12,2) DEFAULT 0.0,
    UNIQUE(year, month, domain, type, category),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_monthly_summaries_period ON monthly_summaries(year, month);

-- 9. BUDGETS
CREATE TABLE budgets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID REFERENCES email_accounts(id),
    category        TEXT NOT NULL,
    monthly_limit   NUMERIC(12,2) NOT NULL,
    annual_limit    NUMERIC(12,2),
    domain          TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(account_id, category)
);

-- 10. SCAN HISTORY (pipeline audit trail)
CREATE TABLE scan_history (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id          UUID REFERENCES email_accounts(id),
    scan_type           TEXT CHECK (scan_type IN ('full', 'incremental', 'historical', 'manual')),
    year                INTEGER,
    start_date          TIMESTAMPTZ,
    end_date            TIMESTAMPTZ,
    query_pattern       TEXT,
    
    -- Counts
    emails_found        INTEGER DEFAULT 0,
    emails_processed    INTEGER DEFAULT 0,
    attachments_found   INTEGER DEFAULT 0,
    attachments_processed INTEGER DEFAULT 0,
    new_transactions    INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    duplicates_skipped  INTEGER DEFAULT 0,
    
    -- Performance
    duration_seconds    NUMERIC(10,2),
    api_calls           INTEGER DEFAULT 0,
    ocr_calls           INTEGER DEFAULT 0,
    llm_calls           INTEGER DEFAULT 0,
    
    -- Status
    status              TEXT DEFAULT 'running'
                        CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    error_message       TEXT,
    notes               TEXT,
    
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scan_history_account ON scan_history(account_id);
CREATE INDEX idx_scan_history_type ON scan_history(scan_type);

-- 11. PIPELINE LOGS (detailed processing steps per email)
CREATE TABLE pipeline_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id        UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    step            TEXT NOT NULL,                  -- scan, download, ocr, extract, classify, store
    status          TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
    input_data      JSONB,
    output_data     JSONB,
    error_message   TEXT,
    duration_ms     INTEGER,
    model_used      TEXT,                           -- For LLM steps
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pipeline_logs_email ON pipeline_logs(email_id);
CREATE INDEX idx_pipeline_logs_step ON pipeline_logs(step);

-- ==========================================================================
-- VIEWS
-- ==========================================================================

-- Main financial view: emails + receipts + transactions
CREATE VIEW financial_full AS
SELECT 
    e.id as email_id,
    e.from_email,
    e.from_name,
    e.subject as email_subject,
    e.email_date,
    e.snippet,
    e.gmail_message_id,
    e.gmail_thread_id,
    ea.label as account_label,
    er.vendor_name,
    er.amount as receipt_amount,
    er.currency,
    er.transaction_date,
    er.confidence_score,
    t.id as transaction_id,
    t.merchant_name,
    t.amount as transaction_amount,
    t.domain,
    t.transaction_type,
    t.category,
    t.tax_category,
    t.is_deductible,
    t.is_recurring,
    t.needs_review,
    t.classification_confidence,
    t.classification_method
FROM emails e
LEFT JOIN email_accounts ea ON e.account_id = ea.id
LEFT JOIN extracted_receipts er ON er.email_id = e.id
LEFT JOIN transactions t ON t.email_id = e.id;

-- Needs review dashboard
CREATE VIEW needs_review AS
SELECT * FROM transactions
WHERE needs_review = TRUE OR domain = 'unknown'
ORDER BY classification_confidence ASC;

-- ==========================================================================
-- FUNCTIONS & TRIGGERS
-- ==========================================================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER emails_updated_at 
    BEFORE UPDATE ON emails 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER transactions_updated_at 
    BEFORE UPDATE ON transactions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Merchant auto-normalize before insert
CREATE OR REPLACE FUNCTION normalize_merchant()
RETURNS TRIGGER AS $$
BEGIN
    -- Try to find a canonical merchant name
    IF NEW.merchant_name IS NOT NULL THEN
        SELECT canonical INTO NEW.merchant_name
        FROM merchant_aliases
        WHERE alias ILIKE NEW.merchant_name
        LIMIT 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transactions_normalize_merchant
    BEFORE INSERT ON transactions
    FOR EACH ROW EXECUTE FUNCTION normalize_merchant();

-- Auto-compute monthly summaries after transaction insert
CREATE OR REPLACE FUNCTION update_monthly_summary()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO monthly_summaries (year, month, domain, type, category, total_amount, count, avg_amount)
    VALUES (
        EXTRACT(YEAR FROM COALESCE(NEW.email_date, NEW.created_at)),
        EXTRACT(MONTH FROM COALESCE(NEW.email_date, NEW.created_at)),
        NEW.domain, NEW.transaction_type, NEW.category,
        NEW.amount, 1, NEW.amount
    )
    ON CONFLICT (year, month, domain, type, category)
    DO UPDATE SET
        total_amount = monthly_summaries.total_amount + NEW.amount,
        count = monthly_summaries.count + 1,
        avg_amount = (monthly_summaries.total_amount + NEW.amount) / (monthly_summaries.count + 1);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER transactions_update_summary
    AFTER INSERT ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_monthly_summary();

-- ==========================================================================
-- ROW LEVEL SECURITY (for multi-account setups)
-- ==========================================================================
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;

-- Default: users can only see their own account's data
CREATE POLICY account_isolation ON emails
    USING (account_id IN (SELECT id FROM email_accounts));

-- ==========================================================================
-- SEED DATA
-- ==========================================================================

-- Default categories — comprehensive taxonomy (kept in sync with db/database.py)
INSERT INTO categories (name, domain, type, tax_relevant, irs_line, sort_order) VALUES
    -- Business income
    ('Client Payments', 'business', 'income', TRUE, 'Line 1', 1),
    ('Product/Service Sales', 'business', 'income', TRUE, 'Line 1', 2),
    ('Consulting Fees', 'business', 'income', TRUE, 'Line 1', 3),
    ('Affiliate Income', 'business', 'income', TRUE, 'Line 1', 4),
    ('Royalties & Licensing', 'business', 'income', TRUE, 'Line 1', 5),
    ('Advertising & Sponsorship Income', 'business', 'income', TRUE, 'Line 1', 6),
    ('Commission Income', 'business', 'income', TRUE, 'Line 1', 7),
    ('Public Speaking', 'business', 'income', TRUE, 'Line 1', 8),
    ('Course & Digital Product Sales', 'business', 'income', TRUE, 'Line 1', 9),
    ('Grants & Subsidies', 'business', 'income', TRUE, 'Line 6', 10),
    ('Business Interest Income', 'business', 'income', TRUE, 'Line 6', 11),
    ('Other Business Income', 'business', 'income', TRUE, 'Line 6', 12),
    -- Personal income
    ('Employment Salary', 'personal', 'income', FALSE, NULL, 30),
    ('Self-Employment Draw', 'personal', 'income', FALSE, NULL, 31),
    ('Investment Income', 'personal', 'income', FALSE, NULL, 32),
    ('Dividend Income', 'personal', 'income', FALSE, NULL, 33),
    ('Interest Income', 'personal', 'income', FALSE, NULL, 34),
    ('Capital Gains', 'personal', 'income', FALSE, NULL, 35),
    ('Rental Income', 'personal', 'income', FALSE, NULL, 36),
    ('Pension & Retirement', 'personal', 'income', FALSE, NULL, 37),
    ('Government Benefits', 'personal', 'income', FALSE, NULL, 38),
    ('Tax Refund', 'personal', 'income', FALSE, NULL, 39),
    ('Gifts Received', 'personal', 'income', FALSE, NULL, 40),
    ('Reimbursements', 'personal', 'income', FALSE, NULL, 41),
    ('Other Personal Income', 'personal', 'income', FALSE, NULL, 42),
    -- Business expenses
    ('Software & Subscriptions', 'business', 'expense', TRUE, 'Line 18', 50),
    ('Web Hosting & Domains', 'business', 'expense', TRUE, 'Line 27a', 51),
    ('Marketing & Advertising', 'business', 'expense', TRUE, 'Line 8', 52),
    ('Online Ads', 'business', 'expense', TRUE, 'Line 8', 53),
    ('Internet & Telecom', 'business', 'expense', TRUE, 'Line 25', 54),
    ('Office Supplies', 'business', 'expense', TRUE, 'Line 18', 55),
    ('Materials & Supplies', 'business', 'expense', TRUE, 'Line 22', 56),
    ('Office Rent', 'business', 'expense', TRUE, 'Line 20b', 57),
    ('Home Office', 'business', 'expense', TRUE, 'Line 30', 58),
    ('Business Travel', 'business', 'expense', TRUE, 'Line 24a', 59),
    ('Meals & Entertainment', 'business', 'expense', TRUE, 'Line 24b', 60),
    ('Travel & Meals', 'business', 'expense', TRUE, 'Line 24', 61),
    ('Vehicle & Auto', 'business', 'expense', TRUE, 'Line 9', 62),
    ('Fuel & Gas (Business)', 'business', 'expense', TRUE, 'Line 9', 63),
    ('Professional Services', 'business', 'expense', TRUE, 'Line 17', 64),
    ('Contractors & Freelancers', 'business', 'expense', TRUE, 'Line 11', 65),
    ('Wages & Payroll', 'business', 'expense', TRUE, 'Line 26', 66),
    ('Employee Benefits', 'business', 'expense', TRUE, 'Line 14', 67),
    ('Business Insurance', 'business', 'expense', TRUE, 'Line 15', 68),
    ('Interest & Bank Fees', 'business', 'expense', TRUE, 'Line 16b', 69),
    ('Merchant & Processing Fees', 'business', 'expense', TRUE, 'Line 27a', 70),
    ('Equipment & Hardware', 'business', 'expense', TRUE, 'Line 13', 71),
    ('Depreciation', 'business', 'expense', TRUE, 'Line 13', 72),
    ('Repairs & Maintenance', 'business', 'expense', TRUE, 'Line 21', 73),
    ('Utilities (Business)', 'business', 'expense', TRUE, 'Line 25', 74),
    ('Licenses & Permits', 'business', 'expense', TRUE, 'Line 23', 75),
    ('Dues & Memberships', 'business', 'expense', TRUE, 'Line 27a', 76),
    ('Education & Training', 'business', 'expense', TRUE, 'Line 27a', 77),
    ('Shipping & Postage', 'business', 'expense', TRUE, 'Line 27a', 78),
    ('Inventory & COGS', 'business', 'expense', TRUE, 'Line 4', 79),
    ('Taxes & Fees (Business)', 'business', 'expense', TRUE, 'Line 23', 80),
    ('Charitable Sponsorship', 'business', 'expense', TRUE, 'Line 27a', 81),
    ('Other Business Expense', 'business', 'expense', TRUE, 'Line 27a', 82),
    -- Personal expenses
    ('Housing & Rent', 'personal', 'expense', FALSE, NULL, 100),
    ('Mortgage', 'personal', 'expense', FALSE, NULL, 101),
    ('Property Tax', 'personal', 'expense', FALSE, NULL, 102),
    ('Home Utilities', 'personal', 'expense', FALSE, NULL, 103),
    ('Home Internet', 'personal', 'expense', FALSE, NULL, 104),
    ('Phone & Mobile', 'personal', 'expense', FALSE, NULL, 105),
    ('Streaming & Subscriptions', 'personal', 'expense', FALSE, NULL, 106),
    ('Groceries', 'personal', 'expense', FALSE, NULL, 107),
    ('Dining Out', 'personal', 'expense', FALSE, NULL, 108),
    ('Coffee Shops', 'personal', 'expense', FALSE, NULL, 109),
    ('Food Delivery', 'personal', 'expense', FALSE, NULL, 110),
    ('Alcohol & Bars', 'personal', 'expense', FALSE, NULL, 111),
    ('Entertainment', 'personal', 'expense', FALSE, NULL, 112),
    ('Gaming', 'personal', 'expense', FALSE, NULL, 113),
    ('Books & Media', 'personal', 'expense', FALSE, NULL, 114),
    ('Hobbies', 'personal', 'expense', FALSE, NULL, 115),
    ('Healthcare', 'personal', 'expense', FALSE, NULL, 116),
    ('Dental', 'personal', 'expense', FALSE, NULL, 117),
    ('Pharmacy & Prescriptions', 'personal', 'expense', FALSE, NULL, 118),
    ('Vision & Optical', 'personal', 'expense', FALSE, NULL, 119),
    ('Personal Insurance', 'personal', 'expense', FALSE, NULL, 120),
    ('Personal Transport', 'personal', 'expense', FALSE, NULL, 121),
    ('Public Transit', 'personal', 'expense', FALSE, NULL, 122),
    ('Rideshare & Taxi', 'personal', 'expense', FALSE, NULL, 123),
    ('Fuel & Gas (Personal)', 'personal', 'expense', FALSE, NULL, 124),
    ('Vehicle Maintenance', 'personal', 'expense', FALSE, NULL, 125),
    ('Parking & Tolls', 'personal', 'expense', FALSE, NULL, 126),
    ('Clothing & Apparel', 'personal', 'expense', FALSE, NULL, 127),
    ('Shopping', 'personal', 'expense', FALSE, NULL, 128),
    ('Electronics & Gadgets', 'personal', 'expense', FALSE, NULL, 129),
    ('Home Improvement', 'personal', 'expense', FALSE, NULL, 130),
    ('Furniture & Appliances', 'personal', 'expense', FALSE, NULL, 131),
    ('Personal Care & Beauty', 'personal', 'expense', FALSE, NULL, 132),
    ('Fitness & Gym', 'personal', 'expense', FALSE, NULL, 133),
    ('Education (Personal)', 'personal', 'expense', FALSE, NULL, 134),
    ('Childcare', 'personal', 'expense', FALSE, NULL, 135),
    ('Kids & Family', 'personal', 'expense', FALSE, NULL, 136),
    ('Pet Care', 'personal', 'expense', FALSE, NULL, 137),
    ('Gifts', 'personal', 'expense', FALSE, NULL, 138),
    ('Charitable Donations', 'personal', 'expense', FALSE, NULL, 139),
    ('Travel & Vacation', 'personal', 'expense', FALSE, NULL, 140),
    ('Hotels & Lodging', 'personal', 'expense', FALSE, NULL, 141),
    ('Banking Fees', 'personal', 'expense', FALSE, NULL, 142),
    ('Loan Payments', 'personal', 'expense', FALSE, NULL, 143),
    ('Credit Card Payments', 'personal', 'expense', FALSE, NULL, 144),
    ('Savings & Investments', 'personal', 'expense', FALSE, NULL, 145),
    ('Taxes (Personal)', 'personal', 'expense', FALSE, NULL, 146),
    ('Social Media', 'personal', 'expense', FALSE, NULL, 147),
    ('E-Commerce', 'personal', 'expense', FALSE, NULL, 148),
    ('Loans & Financing', 'personal', 'expense', FALSE, NULL, 149),
    ('Suspected Scam', 'personal', 'expense', FALSE, NULL, 150),
    ('Other Personal Expense', 'personal', 'expense', FALSE, NULL, 151),
    -- Cross-domain
    ('Transfer', 'both', 'expense', FALSE, NULL, 200),
    ('Refund', 'both', 'income', FALSE, NULL, 201),
    ('Uncategorized', 'both', 'expense', FALSE, NULL, 999);

-- Known merchant aliases
INSERT INTO merchant_aliases (canonical, alias, category, domain) VALUES
    ('Amazon', 'AMZN MKTP US', 'Shopping', 'both'),
    ('Amazon', 'Amazon.com', 'Shopping', 'both'),
    ('Amazon', 'Amazon.ca', 'Shopping', 'both'),
    ('Netflix', 'Netflix.com', 'Entertainment', 'personal'),
    ('Netflix', 'Netflix', 'Entertainment', 'personal'),
    ('Spotify', 'Spotify USA', 'Entertainment', 'personal'),
    ('GitHub', 'GitHub', 'Software & Subscriptions', 'business'),
    ('Slack', 'Slack', 'Software & Subscriptions', 'business'),
    ('AWS', 'Amazon Web Services', 'Internet & Telecom', 'business'),
    ('Google Cloud', 'GCP', 'Internet & Telecom', 'business'),
    ('Hostinger', 'Hostinger', 'Internet & Telecom', 'business'),
    ('Stripe', 'Stripe', 'Client Payments', 'business'),
    ('PayPal', 'PayPal', 'Client Payments', 'both');
