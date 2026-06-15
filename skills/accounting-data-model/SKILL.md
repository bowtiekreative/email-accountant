---
name: accounting-data-model
description: "Core data model and ledger schema for the email accountant. SQLite-backed transaction store with year-based partitioning, balance tracking, and queryable schema."
domain: financial
tags:
  - data-model
  - sqlite
  - ledger
  - schema
  - transactions
  - storage
---

# Accounting Data Model & Ledger

## Overview

The core data model stores all financial transactions in a structured, queryable format using SQLite. Data is organized by year for efficient scanning and reporting, with a complete audit trail from raw email through to categorized transaction.

## Schema

### Core Table: `transactions`

```sql
CREATE TABLE transactions (
    -- Primary key
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Source
    email_id        TEXT UNIQUE,
    email_date      TEXT NOT NULL,          -- ISO 8601
    email_from      TEXT,
    email_subject   TEXT,
    email_snippet   TEXT,
    -- Extracted data
    merchant_name   TEXT,
    merchant_email  TEXT,
    amount          REAL,
    currency        TEXT DEFAULT 'CAD',
    transaction_date TEXT,                   -- Date from receipt/email
    description     TEXT,
    line_items      TEXT,                   -- JSON array of items
    -- Classification
    domain          TEXT CHECK(domain IN ('personal', 'business', 'unknown')),
    type            TEXT CHECK(type IN ('income', 'expense', 'transfer', 'unknown')),
    category        TEXT,
    subcategory     TEXT,
    tax_category    TEXT,                   -- IRS Schedule C line
    classification_confidence REAL DEFAULT 0.0,
    classification_method TEXT,             -- 'rule', 'llm', 'manual'
    -- Receipt / attachment
    attachment_path TEXT,
    receipt_ocr_text TEXT,
    -- Flags
    needs_review    INTEGER DEFAULT 0,
    reviewed        INTEGER DEFAULT 0,
    flagged         INTEGER DEFAULT 0,
    is_recurring    INTEGER DEFAULT 0,
    is_deductible   INTEGER DEFAULT 0,
    -- Deduction rate (e.g. 0.5 for meals)
    deduction_rate  REAL DEFAULT 0.0,
    -- Timestamps
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    scan_year       INTEGER NOT NULL        -- Partition key
);
```

### Supporting Tables

```sql
-- Merchant aliases (normalize vendor names)
CREATE TABLE merchant_aliases (
    id          INTEGER PRIMARY KEY,
    canonical   TEXT NOT NULL,               -- Normalized name
    alias       TEXT NOT NULL UNIQUE,        -- Raw variant from email/receipt
    category    TEXT,
    domain      TEXT
);

-- Categories hierarchy
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    parent_id   INTEGER REFERENCES categories(id),
    domain      TEXT CHECK(domain IN ('personal', 'business', 'both')),
    type        TEXT CHECK(type IN ('income', 'expense', 'both')),
    tax_relevant INTEGER DEFAULT 0,
    irs_line    TEXT                        -- IRS Schedule C line reference
);

-- Monthly summaries (pre-computed for reports)
CREATE TABLE monthly_summaries (
    id          INTEGER PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    domain      TEXT NOT NULL,
    type        TEXT NOT NULL,
    category    TEXT,
    total_amount REAL DEFAULT 0.0,
    count       INTEGER DEFAULT 0,
    UNIQUE(year, month, domain, type, category)
);

-- Scan history (track what's been processed)
CREATE TABLE scan_history (
    id              INTEGER PRIMARY KEY,
    scan_date       TEXT DEFAULT (datetime('now')),
    scan_type       TEXT CHECK(scan_type IN ('full', 'incremental', 'year')),
    year            INTEGER,
    emails_found    INTEGER DEFAULT 0,
    emails_processed INTEGER DEFAULT 0,
    attachments_found  INTEGER DEFAULT 0,
    new_transactions    INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    duration_seconds    REAL
);
```

## Year-Based Partitioning

Data is organized by year for efficient querying and to handle the constraint that financial data naturally rolls up annually.

```python
def get_db_path(year, base_dir='data'):
    """Get the database path for a specific year."""
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, f'ledger_{year}.db')

def init_year_db(year, base_dir='data'):
    """Initialize a SQLite database for a specific year."""
    db_path = get_db_path(year, base_dir)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    
    # Create tables
    conn.executescript(SCHEMA_SQL)  # Full schema from above
    
    conn.commit()
    return conn
```

## Inserting Transactions

```python
def insert_transaction(conn, tx_data):
    """Insert a new transaction with dedup by email_id."""
    tx_data['scan_year'] = int(tx_data.get('email_date', '2026')[:4])
    
    # Dedup check
    if tx_data.get('email_id'):
        existing = conn.execute(
            'SELECT id FROM transactions WHERE email_id = ?',
            (tx_data['email_id'],)
        ).fetchone()
        if existing:
            # Update instead — email was re-scanned (enrichment)
            return update_transaction(conn, existing[0], tx_data)
    
    # Auto-categorize deductible
    tx_data['is_deductible'] = 1 if (
        tx_data.get('domain') == 'business' 
        and tx_data.get('type') == 'expense'
    ) else 0
    
    # Deduction rate for meals
    if tx_data.get('tax_category') in ('Meals/Entertainment', 'Travel/Gifts'):
        tx_data['deduction_rate'] = 0.5
    
    conn.execute('''
        INSERT INTO transactions (
            email_id, email_date, email_from, email_subject, email_snippet,
            merchant_name, merchant_email, amount, currency, transaction_date,
            description, line_items, domain, type, category, subcategory,
            tax_category, classification_confidence, classification_method,
            attachment_path, receipt_ocr_text, needs_review,
            is_deductible, deduction_rate, scan_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', tuple(tx_data.get(k) for k in [
        'email_id', 'email_date', 'email_from', 'email_subject', 'email_snippet',
        'merchant_name', 'merchant_email', 'amount', 'currency', 'transaction_date',
        'description', 'line_items', 'domain', 'type', 'category', 'subcategory',
        'tax_category', 'classification_confidence', 'classification_method',
        'attachment_path', 'receipt_ocr_text', 'needs_review',
        'is_deductible', 'deduction_rate', 'scan_year'
    ]))
    
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]
```

## Query Patterns

### Yearly Summary
```sql
SELECT category, type, COUNT(*) as count, SUM(amount) as total
FROM transactions
WHERE scan_year = ?
GROUP BY category, type
ORDER BY total DESC;
```

### Uncategorized / Needs Review
```sql
SELECT * FROM transactions
WHERE domain = 'unknown' OR needs_review = 1
ORDER BY classification_confidence ASC
LIMIT 50;
```

### Income by Month
```sql
SELECT strftime('%Y-%m', email_date) as month, 
       SUM(amount) as total_income, COUNT(*) as count
FROM transactions
WHERE type = 'income' AND domain = 'business'
GROUP BY month
ORDER BY month;
```

### Recurring Expenses
```sql
SELECT merchant_name, amount, COUNT(*) as occurrences
FROM transactions
WHERE type = 'expense'
GROUP BY merchant_name, ROUND(amount, 2)
HAVING occurrences > 3
ORDER BY occurrences DESC;
```

### Search Transactions
```sql
SELECT * FROM transactions
WHERE merchant_name LIKE ? OR description LIKE ? OR category LIKE ?
ORDER BY email_date DESC;
```

## Data Export

```python
def export_to_csv(year, output_path, domain=None):
    """Export transactions to CSV for spreadsheet/Excel import."""
    import csv
    conn = sqlite3.connect(get_db_path(year))
    conn.row_factory = sqlite3.Row
    
    query = 'SELECT * FROM transactions WHERE 1=1'
    params = []
    if domain:
        query += ' AND domain = ?'
        params.append(domain)
    query += ' ORDER BY email_date'
    
    rows = conn.execute(query, params).fetchall()
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([row[k] for k in rows[0].keys()])
    
    return output_path


def export_to_json(year, output_path):
    """Export to JSON for programmatic use."""
    import json
    conn = sqlite3.connect(get_db_path(year))
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute(
        'SELECT * FROM transactions ORDER BY email_date'
    ).fetchall()
    
    with open(output_path, 'w') as f:
        json.dump([dict(r) for r in rows], f, indent=2, default=str)
    
    return output_path
```

## GOTCHAs

- SQLite WAL mode prevents lock contention during concurrent reads but writes still serialize
- Year-based partitioning: migration needed if you backfill a year that already has a DB
- Email ID dedup: Gmail message IDs are unique per message, NOT per email thread. Each email in a thread has a different ID
- Amount precision: use REAL (floating) for SQLite amounts. Round to 2 decimal places at display time, not storage time
- `needs_review` flag: set when classification_confidence < 0.5 OR domain='unknown' — batch these for user review
- Merchant aliases: "AMZN MKTP US" should normalize to "Amazon" — keep the alias table populated as you discover variants
- Schema migrations: since data is year-partitioned, you can add columns per year independently. Use COALESCE in cross-year queries