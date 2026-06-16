"""Learn-from-edits: a manual re-categorization in the Review queue becomes a
durable merchant rule, and is applied retroactively to past transactions from
the same merchant (that you haven't manually reviewed)."""

import glob
import os
import sqlite3
from typing import Any, Optional

from .config import DB_DIR

_MAIN_DB = os.path.join(DB_DIR, "email_accountant.db")


def _main_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_MAIN_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS learned_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_key TEXT UNIQUE NOT NULL,
            merchant_label TEXT,
            domain TEXT, tx_type TEXT, category TEXT,
            hits INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')))"""
    )
    conn.commit()
    return conn


def record_rule(merchant: str, domain: Optional[str], tx_type: Optional[str],
                category: Optional[str]) -> None:
    """Upsert a merchant→classification rule from a manual correction."""
    key = (merchant or "").strip().lower()
    if not key:
        return
    conn = _main_conn()
    existing = conn.execute(
        "SELECT id FROM learned_rules WHERE merchant_key = ?", (key,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE learned_rules SET domain=COALESCE(?,domain), "
            "tx_type=COALESCE(?,tx_type), category=COALESCE(?,category), "
            "merchant_label=?, hits=hits+1, updated_at=datetime('now') WHERE id=?",
            (domain, tx_type, category, merchant, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO learned_rules (merchant_key, merchant_label, domain, tx_type, category, hits) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (key, merchant, domain, tx_type, category),
        )
    conn.commit()
    conn.close()


def apply_rule_to_history(merchant: str, domain: Optional[str], tx_type: Optional[str],
                          category: Optional[str], exclude_id: Optional[int] = None) -> int:
    """Update past transactions from this merchant that you haven't reviewed.

    Returns the number of transactions updated across all year ledgers.
    """
    key = (merchant or "").strip().lower()
    if not key:
        return 0

    sets, params = [], []
    if domain:
        sets.append("domain = ?"); params.append(domain)
    if tx_type:
        sets.append("transaction_type = ?"); params.append(tx_type)
    if category:
        sets.append("category = ?"); params.append(category)
    if not sets:
        return 0
    sets.append("classification_method = 'learned'")
    sets.append("needs_review = 0")
    set_clause = ", ".join(sets)

    total = 0
    for path in glob.glob(os.path.join(DB_DIR, "email_accountant*.db")):
        conn = sqlite3.connect(path)
        try:
            has = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone()
            if not has:
                continue
            where = "lower(merchant_name) = ? AND reviewed = 0"
            args = list(params) + [key]
            if exclude_id is not None:
                where += " AND id != ?"
                args.append(exclude_id)
            cur = conn.execute(
                f"UPDATE transactions SET {set_clause} WHERE {where}", args
            )
            total += cur.rowcount
            conn.commit()
        finally:
            conn.close()
    return total


def learn_from_edit(merchant: str, changes: dict[str, Any],
                    exclude_id: Optional[int] = None) -> dict[str, Any]:
    """Called after a manual transaction edit. Records the rule and backfills."""
    domain = changes.get("domain")
    tx_type = changes.get("transaction_type")
    category = changes.get("category")
    if not (domain or tx_type or category) or not merchant:
        return {"learned": False, "updated_past": 0}

    record_rule(merchant, domain, tx_type, category)
    # Reload the in-process classifier cache so new scans pick it up too.
    try:
        from pipeline.processor import load_learned_rules
        load_learned_rules(force=True)
    except Exception:
        pass
    updated = apply_rule_to_history(merchant, domain, tx_type, category, exclude_id)
    return {"learned": True, "merchant": merchant, "updated_past": updated}


def list_rules() -> list[dict[str, Any]]:
    conn = _main_conn()
    rows = conn.execute(
        "SELECT merchant_label, domain, tx_type, category, hits, updated_at "
        "FROM learned_rules ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
