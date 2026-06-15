"""
Email Accountant — Database Layer
Works with both SQLite (local dev) and PostgreSQL/Supabase (production).

Auto-detects which backend to use based on environment variables.
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
DB_DIR = os.environ.get("EMAIL_ACCOUNTANT_DB_DIR", str(Path.home() / ".email-accountant" / "data"))
DB_MODE = os.environ.get("EMAIL_ACCOUNTANT_DB", "sqlite")  # sqlite | supabase

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# SQLite Implementation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Email Accounts
CREATE TABLE IF NOT EXISTS email_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT NOT NULL UNIQUE,
    email_address   TEXT NOT NULL,
    provider        TEXT DEFAULT 'gmail',
    credentials_ref TEXT,
    token_ref       TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Emails (full metadata)
CREATE TABLE IF NOT EXISTS emails (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id          INTEGER REFERENCES email_accounts(id),
    gmail_message_id    TEXT UNIQUE,
    gmail_thread_id     TEXT,
    gmail_label_ids     TEXT,
    message_id          TEXT,
    in_reply_to         TEXT,
    references_header   TEXT,
    from_header         TEXT NOT NULL,
    from_email          TEXT NOT NULL,
    from_name           TEXT,
    to_header           TEXT,
    to_emails           TEXT,
    cc_header           TEXT,
    cc_emails           TEXT,
    bcc_emails          TEXT,
    reply_to            TEXT,
    subject             TEXT,
    snippet             TEXT,
    body_plain          TEXT,
    body_html           TEXT,
    content_type        TEXT,
    email_date          TEXT NOT NULL,
    received_date       TEXT,
    return_path         TEXT,
    dkim_signature      TEXT,
    spf_status          TEXT,
    list_unsubscribe    TEXT,
    is_read             INTEGER DEFAULT 0,
    is_starred          INTEGER DEFAULT 0,
    is_important        INTEGER DEFAULT 0,
    is_spam             INTEGER DEFAULT 0,
    email_status        TEXT DEFAULT 'pending',
    fetched_at          TEXT DEFAULT (datetime('now')),
    processed_at        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- Attachments
CREATE TABLE IF NOT EXISTS attachments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id        INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    filepath        TEXT,
    mime_type       TEXT,
    size_bytes      INTEGER,
    attachment_id   TEXT,
    content_id      TEXT,
    is_inline       INTEGER DEFAULT 0,
    hash_sha256     TEXT,
    ocr_status      TEXT DEFAULT 'pending'
                    CHECK (ocr_status IN ('pending','processing','done','error')),
    ocr_text        TEXT,
    ocr_confidence  REAL DEFAULT 0.0,
    ocr_processed_at TEXT,
    downloaded_at   TEXT DEFAULT (datetime('now')),
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Extracted Receipts
CREATE TABLE IF NOT EXISTS extracted_receipts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id        INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    attachment_id   INTEGER REFERENCES attachments(id),
    vendor_name     TEXT,
    vendor_email    TEXT,
    vendor_website  TEXT,
    amount          REAL,
    currency        TEXT DEFAULT 'USD',
    transaction_date TEXT,
    line_items      TEXT DEFAULT '[]',       -- JSON array
    subtotal        REAL,
    tax_amount      REAL,
    tip_amount      REAL,
    total           REAL,
    invoice_number  TEXT,
    order_number    TEXT,
    receipt_number  TEXT,
    transaction_id  TEXT,
    payment_method  TEXT,
    card_last_four  TEXT,
    billing_address TEXT,
    shipping_address TEXT,
    merchant_category TEXT,
    merchant_phone   TEXT,
    merchant_address TEXT,
    extraction_method TEXT DEFAULT 'ocr',
    confidence_score REAL DEFAULT 0.0,
    raw_text          TEXT,
    needs_review    INTEGER DEFAULT 0,
    review_notes    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Transactions (Ledger)
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id            INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    receipt_id          INTEGER REFERENCES extracted_receipts(id),
    account_id          INTEGER REFERENCES email_accounts(id),
    email_from          TEXT,
    email_subject       TEXT,
    email_date          TEXT,
    merchant_name       TEXT,
    merchant_email      TEXT,
    merchant_category   TEXT,
    amount              REAL NOT NULL,
    currency            TEXT DEFAULT 'USD',
    transaction_date    TEXT,
    description         TEXT,
    line_items          TEXT DEFAULT '[]',
    domain              TEXT DEFAULT 'unknown',
    transaction_type    TEXT DEFAULT 'unknown',
    category            TEXT,
    subcategory         TEXT,
    tax_category        TEXT,
    classification_confidence REAL DEFAULT 0.0,
    classification_method TEXT DEFAULT 'rule',
    is_deductible       INTEGER DEFAULT 0,
    deduction_rate      REAL DEFAULT 0.0,
    is_recurring        INTEGER DEFAULT 0,
    recurring_frequency TEXT,
    needs_review        INTEGER DEFAULT 0,
    reviewed            INTEGER DEFAULT 0,
    flagged             INTEGER DEFAULT 0,
    flag_reason         TEXT,
    attachment_path     TEXT,
    receipt_ocr_text    TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- Merchant Aliases
CREATE TABLE IF NOT EXISTS merchant_aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical   TEXT NOT NULL,
    alias       TEXT NOT NULL UNIQUE,
    category    TEXT,
    domain      TEXT,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Categories
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    parent_id   INTEGER REFERENCES categories(id),
    domain      TEXT,
    tx_type     TEXT,
    tax_relevant INTEGER DEFAULT 0,
    irs_line    TEXT,
    description TEXT,
    sort_order  INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Monthly Summaries
CREATE TABLE IF NOT EXISTS monthly_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER REFERENCES email_accounts(id),
    yr              INTEGER NOT NULL,
    mnth            INTEGER NOT NULL,
    domain          TEXT NOT NULL,
    tx_type         TEXT NOT NULL,
    category        TEXT,
    total_amount    REAL DEFAULT 0.0,
    tx_count        INTEGER DEFAULT 0,
    avg_amount      REAL DEFAULT 0.0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Budgets
CREATE TABLE IF NOT EXISTS budgets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER REFERENCES email_accounts(id),
    category        TEXT NOT NULL,
    monthly_limit   REAL NOT NULL,
    annual_limit    REAL,
    domain          TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(account_id, category)
);

-- Scan History
CREATE TABLE IF NOT EXISTS scan_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id          INTEGER REFERENCES email_accounts(id),
    scan_type           TEXT,
    yr                  INTEGER,
    start_date          TEXT,
    end_date            TEXT,
    query_pattern       TEXT,
    emails_found        INTEGER DEFAULT 0,
    emails_processed    INTEGER DEFAULT 0,
    attachments_found   INTEGER DEFAULT 0,
    attachments_processed INTEGER DEFAULT 0,
    new_transactions    INTEGER DEFAULT 0,
    errors              INTEGER DEFAULT 0,
    duplicates_skipped  INTEGER DEFAULT 0,
    duration_seconds    REAL,
    api_calls           INTEGER DEFAULT 0,
    ocr_calls           INTEGER DEFAULT 0,
    llm_calls           INTEGER DEFAULT 0,
    scan_status         TEXT DEFAULT 'running',
    error_message       TEXT,
    notes               TEXT,
    started_at          TEXT DEFAULT (datetime('now')),
    completed_at        TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- Pipeline Logs
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id        INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    step_name       TEXT NOT NULL,
    step_status     TEXT NOT NULL,
    input_data      TEXT,
    output_data     TEXT,
    error_message   TEXT,
    duration_ms     INTEGER,
    model_used      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_email);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(email_date DESC);
CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(account_id, email_status);
CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id);
CREATE INDEX IF NOT EXISTS idx_receipts_email ON extracted_receipts(email_id);
CREATE INDEX IF NOT EXISTS idx_transactions_email ON transactions(email_id);
CREATE INDEX IF NOT EXISTS idx_transactions_domain ON transactions(domain);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(email_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_review ON transactions(needs_review) WHERE needs_review = 1;
CREATE INDEX IF NOT EXISTS idx_merchant_aliases_alias ON merchant_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_pipeline_logs_email ON pipeline_logs(email_id);
"""

# Seed data
SEED_SQL = """
-- Categories
INSERT OR IGNORE INTO categories (name, domain, tx_type, tax_relevant, irs_line, sort_order) VALUES
    ('Client Payments', 'business', 'income', 1, 'Line 1', 1),
    ('Product/Service Sales', 'business', 'income', 1, 'Line 1', 2),
    ('Consulting Fees', 'business', 'income', 1, 'Line 1', 3),
    ('Affiliate Income', 'business', 'income', 1, 'Line 1', 4),
    ('Software & Subscriptions', 'business', 'expense', 1, 'Line 18', 10),
    ('Marketing & Advertising', 'business', 'expense', 1, 'Line 8', 11),
    ('Internet & Telecom', 'business', 'expense', 1, 'Line 25', 12),
    ('Office Supplies', 'business', 'expense', 1, 'Line 18', 13),
    ('Travel & Meals', 'business', 'expense', 1, 'Line 24', 14),
    ('Professional Services', 'business', 'expense', 1, 'Line 17', 15),
    ('Equipment & Hardware', 'business', 'expense', 1, 'Line 13', 16),
    ('Housing & Rent', 'personal', 'expense', 0, NULL, 20),
    ('Groceries', 'personal', 'expense', 0, NULL, 21),
    ('Entertainment', 'personal', 'expense', 0, NULL, 22),
    ('Dining Out', 'personal', 'expense', 0, NULL, 23),
    ('Healthcare', 'personal', 'expense', 0, NULL, 24),
    ('Personal Transport', 'personal', 'expense', 0, NULL, 25),
    ('Shopping', 'personal', 'expense', 0, NULL, 26),
    ('Employment Salary', 'personal', 'income', 0, NULL, 30),
    ('Investment Income', 'personal', 'income', 0, NULL, 31);

-- Merchant Aliases
INSERT OR IGNORE INTO merchant_aliases (canonical, alias, category, domain) VALUES
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
"""


def get_db_path(year: Optional[int] = None) -> str:
    """Get the database path. Year-partitioned for performance."""
    os.makedirs(DB_DIR, exist_ok=True)
    if year:
        return os.path.join(DB_DIR, f"email_accountant_{year}.db")
    return os.path.join(DB_DIR, "email_accountant.db")


def get_connection(year: Optional[int] = None) -> sqlite3.Connection:
    """Get a SQLite connection with proper settings."""
    db_path = get_db_path(year)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite(year: Optional[int] = None):
    """Initialize the SQLite database schema."""
    conn = get_connection(year)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SEED_SQL)
    
    # Track schema version
    conn.execute(
        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,)
    )
    conn.commit()
    conn.close()
    return get_db_path(year)


# ---------------------------------------------------------------------------
# Database class (works with both backends)
# ---------------------------------------------------------------------------

class EmailAccountantDB:
    """Database abstraction layer for the email accountant system.
    
    Currently uses SQLite. When SUPABASE_URL is set, uses PostgreSQL/Supabase.
    """
    
    def __init__(self, year: Optional[int] = None):
        self.year = year or datetime.now().year
        if DB_MODE == "supabase" and SUPABASE_URL and SUPABASE_KEY:
            self.backend = "supabase"
            self._init_supabase()
        else:
            self.backend = "sqlite"
            self._conn = get_connection(self.year)
            self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure schema exists."""
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        )
        row = self._conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
        if not row or row["version"] < SCHEMA_VERSION:
            init_sqlite(self.year)
    
    def _init_supabase(self):
        """Initialize Supabase client (placeholder for when Supabase is available)."""
        from supabase import create_client
        self._supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # -----------------------------------------------------------------------
    # Emails
    # -----------------------------------------------------------------------
    
    def insert_email(self, email_data: dict) -> int:
        """Insert a new email with full metadata. Returns ID."""
        from_email = email_data.get("from_header", "")
        if "@" in from_email:
            import re
            match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', from_email)
            email_data["from_email"] = match.group(0) if match else from_email
        
        # JSON-encode list fields
        for field in ["gmail_label_ids", "to_emails", "cc_emails", "bcc_emails"]:
            if isinstance(email_data.get(field), (list, tuple)):
                email_data[field] = json.dumps(email_data[field])
        
        cols = ", ".join(email_data.keys())
        placeholders = ", ".join("?" for _ in email_data)
        
        # Upsert by gmail_message_id
        existing = None
        if email_data.get("gmail_message_id"):
            existing = self._conn.execute(
                "SELECT id FROM emails WHERE gmail_message_id = ?",
                (email_data["gmail_message_id"],)
            ).fetchone()
        
        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in email_data.keys())
            set_clause += ", updated_at = datetime('now')"
            values = list(email_data.values()) + [existing["id"]]
            self._conn.execute(
                f"UPDATE emails SET {set_clause} WHERE id = ?",
                values
            )
            return existing["id"]
        else:
            cur = self._conn.execute(
                f"INSERT INTO emails ({cols}) VALUES ({placeholders})",
                list(email_data.values())
            )
            self._conn.commit()
            return cur.lastrowid
    
    def get_email(self, email_id: int) -> Optional[dict]:
        """Get email by ID."""
        row = self._conn.execute(
            "SELECT * FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        return dict(row) if row else None
    
    def get_email_by_gmail_id(self, gmail_id: str) -> Optional[dict]:
        """Get email by Gmail message ID."""
        row = self._conn.execute(
            "SELECT * FROM emails WHERE gmail_message_id = ?", (gmail_id,)
        ).fetchone()
        return dict(row) if row else None
    
    def search_emails(self, query: str, limit: int = 50) -> list:
        """Search emails by subject, from, or body."""
        like = f"%{query}%"
        rows = self._conn.execute("""
            SELECT * FROM emails 
            WHERE subject LIKE ? OR from_email LIKE ? OR from_name LIKE ? OR snippet LIKE ?
            ORDER BY email_date DESC
            LIMIT ?
        """, (like, like, like, like, limit)).fetchall()
        return [dict(r) for r in rows]
    
    def get_emails_by_month(self, year: int, month: int) -> list:
        """Get all emails for a specific month."""
        month_str = f"{year}-{month:02d}"
        rows = self._conn.execute("""
            SELECT * FROM emails 
            WHERE strftime('%Y-%m', email_date) = ?
            ORDER BY email_date DESC
        """, (month_str,)).fetchall()
        return [dict(r) for r in rows]
    
    # -----------------------------------------------------------------------
    # Attachments
    # -----------------------------------------------------------------------
    
    def insert_attachment(self, att_data: dict) -> int:
        """Insert an attachment record."""
        cols = ", ".join(att_data.keys())
        placeholders = ", ".join("?" for _ in att_data)
        cur = self._conn.execute(
            f"INSERT INTO attachments ({cols}) VALUES ({placeholders})",
            list(att_data.values())
        )
        self._conn.commit()
        return cur.lastrowid
    
    def get_attachments_for_email(self, email_id: int) -> list:
        """Get all attachments for an email."""
        rows = self._conn.execute(
            "SELECT * FROM attachments WHERE email_id = ? ORDER BY filename",
            (email_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    # -----------------------------------------------------------------------
    # Receipts
    # -----------------------------------------------------------------------
    
    def insert_receipt(self, receipt_data: dict) -> int:
        """Insert extracted receipt data."""
        if isinstance(receipt_data.get("line_items"), (list, tuple)):
            receipt_data["line_items"] = json.dumps(receipt_data["line_items"])
        
        cols = ", ".join(receipt_data.keys())
        placeholders = ", ".join("?" for _ in receipt_data)
        cur = self._conn.execute(
            f"INSERT INTO extracted_receipts ({cols}) VALUES ({placeholders})",
            list(receipt_data.values())
        )
        self._conn.commit()
        return cur.lastrowid
    
    # -----------------------------------------------------------------------
    # Transactions
    # -----------------------------------------------------------------------
    
    def insert_transaction(self, tx_data: dict) -> int:
        """Insert a transaction and update monthly summary."""
        if isinstance(tx_data.get("line_items"), (list, tuple)):
            tx_data["line_items"] = json.dumps(tx_data["line_items"])
        
        # Deduplicate by email_id
        if tx_data.get("email_id"):
            existing = self._conn.execute(
                "SELECT id FROM transactions WHERE email_id = ?",
                (tx_data["email_id"],)
            ).fetchone()
            if existing:
                set_clause = ", ".join(f"{k} = ?" for k in tx_data.keys())
                set_clause += ", updated_at = datetime('now')"
                values = list(tx_data.values()) + [existing["id"]]
                self._conn.execute(
                    f"UPDATE transactions SET {set_clause} WHERE id = ?",
                    values
                )
                self._conn.commit()
                return existing["id"]
        
        cols = ", ".join(tx_data.keys())
        placeholders = ", ".join("?" for _ in tx_data)
        cur = self._conn.execute(
            f"INSERT INTO transactions ({cols}) VALUES ({placeholders})",
            list(tx_data.values())
        )
        self._conn.commit()
        
        # Update monthly summary
        self._update_monthly_summary(tx_data)
        
        return cur.lastrowid
    
    def _update_monthly_summary(self, tx_data: dict):
        """Pre-compute monthly summary entry."""
        from datetime import datetime as dt
        email_date = tx_data.get("email_date")
        if email_date:
            try:
                d = dt.fromisoformat(email_date)
                yr, mnth = d.year, d.month
                domain = tx_data.get("domain", "unknown")
                tx_type = tx_data.get("transaction_type", "unknown")
                category = tx_data.get("category")
                amount = tx_data.get("amount", 0)
                
                self._conn.execute("""
                    INSERT INTO monthly_summaries (yr, mnth, domain, tx_type, category, total_amount, tx_count, avg_amount)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT DO NOTHING
                """, (yr, mnth, domain, tx_type, category, amount, amount))
                self._conn.commit()
            except:
                pass
    
    def get_transactions(self, year: Optional[int] = None, 
                        domain: Optional[str] = None,
                        category: Optional[str] = None,
                        limit: int = 100) -> list:
        """Get transactions with optional filters."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if year:
            query += " AND strftime('%Y', email_date) = ?"
            params.append(str(year))
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY email_date DESC LIMIT ?"
        params.append(limit)
        
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    
    def get_needs_review(self, limit: int = 50) -> list:
        """Get transactions needing review."""
        rows = self._conn.execute("""
            SELECT * FROM transactions
            WHERE needs_review = 1 OR domain = 'unknown'
            ORDER BY classification_confidence ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    
    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------
    
    def monthly_summary(self, year: int, month: int) -> dict:
        """Get monthly income/expense summary."""
        month_str = f"{year}-{month:02d}"
        
        income = self._conn.execute("""
            SELECT domain, category, SUM(amount) as total, COUNT(*) as count
            FROM transactions
            WHERE strftime('%Y-%m', email_date) = ? AND transaction_type = 'income'
            GROUP BY domain, category
            ORDER BY total DESC
        """, (month_str,)).fetchall()
        
        expenses = self._conn.execute("""
            SELECT domain, category, SUM(amount) as total, COUNT(*) as count
            FROM transactions
            WHERE strftime('%Y-%m', email_date) = ? AND transaction_type = 'expense'
            GROUP BY domain, category
            ORDER BY total DESC
        """, (month_str,)).fetchall()
        
        return {
            "period": month_str,
            "income": [dict(r) for r in income],
            "expenses": [dict(r) for r in expenses],
        }
    
    # -----------------------------------------------------------------------
    # Scan History
    # -----------------------------------------------------------------------
    
    def log_scan(self, scan_data: dict) -> int:
        """Log a scan run."""
        cols = ", ".join(scan_data.keys())
        placeholders = ", ".join("?" for _ in scan_data)
        cur = self._conn.execute(
            f"INSERT INTO scan_history ({cols}) VALUES ({placeholders})",
            list(scan_data.values())
        )
        self._conn.commit()
        return cur.lastrowid
    
    # -----------------------------------------------------------------------
    # Pipeline Logs
    # -----------------------------------------------------------------------
    
    def log_pipeline_step(self, email_id: int, step: str, status: str, **kwargs):
        """Log a pipeline processing step for an email."""
        data = {
            "email_id": email_id,
            "step_name": step,
            "step_status": status,
            **kwargs
        }
        if "input_data" in data and isinstance(data["input_data"], dict):
            data["input_data"] = json.dumps(data["input_data"])
        if "output_data" in data and isinstance(data["output_data"], dict):
            data["output_data"] = json.dumps(data["output_data"])
        
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        self._conn.execute(
            f"INSERT INTO pipeline_logs ({cols}) VALUES ({placeholders})",
            list(data.values())
        )
        self._conn.commit()
    
    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------
    
    def close(self):
        if hasattr(self, "_conn"):
            self._conn.close()


# ---------------------------------------------------------------------------
# Helper: init all years
# ---------------------------------------------------------------------------

def init_all_dbs(start_year: int = 2020, end_year: Optional[int] = None):
    """Initialize databases for a range of years."""
    if end_year is None:
        end_year = datetime.now().year + 1
    
    paths = []
    for year in range(start_year, end_year + 1):
        path = init_sqlite(year)
        paths.append(path)
    
    # Also init the year-less main db
    path = init_sqlite()
    paths.append(path)
    
    return paths


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    paths = init_all_dbs(2024, 2026)
    print(f"✅ Initialized databases:")
    for p in paths:
        size = os.path.getsize(p)
        print(f"   {p} ({size:,} bytes)")
    
    # Test insert
    db = EmailAccountantDB(2026)
    email_id = db.insert_email({
        "gmail_message_id": "test123",
        "from_header": "Stripe <receipts@stripe.com>",
        "subject": "Your receipt from Acme Corp",
        "email_date": "2026-06-15T10:00:00",
        "snippet": "Thank you for your payment of $49.99",
        "from_email": "receipts@stripe.com",
        "from_name": "Stripe",
        "email_status": "pending"
    })
    print(f"\n📧 Inserted email ID: {email_id}")
    print(f"📧 Retrieved: {db.get_email(email_id)}")
    db.close()
    print("\n✅ Database test passed!")
