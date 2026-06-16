"""Read/write access to the year-partitioned SQLite ledgers.

The engine (db/database.py) writes one SQLite file per year
(email_accountant_2025.db, ...) plus a main email_accountant.db. This module
unions across all of them for reads and routes writes to the correct file.

Transaction IDs are only unique within a single file, so the API exposes a
composite id of the form "<db-stem>:<rowid>" (e.g. "email_accountant_2025:42").
"""

import glob
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

from .config import DB_DIR

# Columns the review UI is allowed to edit.
EDITABLE_FIELDS = {
    "domain",
    "transaction_type",
    "category",
    "subcategory",
    "tax_category",
    "merchant_name",
    "amount",
    "is_deductible",
    "deduction_rate",
    "needs_review",
    "reviewed",
    "flagged",
    "flag_reason",
}


def _db_files() -> list[str]:
    """All ledger files, sorted so the main db comes first then years asc."""
    files = glob.glob(os.path.join(DB_DIR, "email_accountant*.db"))
    return sorted(files)


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


@contextmanager
def _connect(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _has_transactions_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    return row is not None


def available_years() -> list[int]:
    years: set[int] = set()
    for path in _db_files():
        with _connect(path) as conn:
            if not _has_transactions_table(conn):
                continue
            for row in conn.execute(
                "SELECT DISTINCT substr(email_date,1,4) AS y FROM transactions "
                "WHERE email_date IS NOT NULL"
            ):
                if row["y"] and row["y"].isdigit():
                    years.add(int(row["y"]))
    return sorted(years, reverse=True)


def _row_to_tx(row: sqlite3.Row, stem: str) -> dict[str, Any]:
    d = dict(row)
    d["id"] = f"{stem}:{d['id']}"
    return d


def list_transactions(
    year: Optional[int] = None,
    domain: Optional[str] = None,
    tx_type: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    needs_review: Optional[bool] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if year:
        where.append("substr(email_date,1,4) = ?")
        params.append(str(year))
    if domain:
        where.append("domain = ?")
        params.append(domain)
    if tx_type:
        where.append("transaction_type = ?")
        params.append(tx_type)
    if category:
        where.append("category = ?")
        params.append(category)
    if needs_review is not None:
        where.append("(needs_review = ? OR domain = 'unknown')" if needs_review else "needs_review = 0")
        if needs_review:
            params.append(1)
    if q:
        where.append("(merchant_name LIKE ? OR email_subject LIKE ? OR description LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    clause = " AND ".join(where)
    results: list[dict[str, Any]] = []
    for path in _db_files():
        with _connect(path) as conn:
            if not _has_transactions_table(conn):
                continue
            stem = _stem(path)
            rows = conn.execute(
                f"SELECT * FROM transactions WHERE {clause} ORDER BY email_date DESC",
                params,
            ).fetchall()
            results.extend(_row_to_tx(r, stem) for r in rows)

    # Dedup across the main db + year db (same email can appear in both).
    seen: dict[tuple, dict] = {}
    for tx in results:
        key = (tx.get("email_id"), tx.get("email_subject"), tx.get("amount"))
        if key not in seen:
            seen[key] = tx
    deduped = sorted(
        seen.values(), key=lambda t: (t.get("email_date") or ""), reverse=True
    )
    return deduped[offset : offset + limit]


def overview(year: Optional[int] = None) -> dict[str, Any]:
    """Aggregate dashboard numbers across all ledgers for a year (or all)."""
    txs = list_transactions(year=year, limit=1_000_000)

    income = sum(t["amount"] for t in txs if t.get("transaction_type") == "income")
    expense = sum(t["amount"] for t in txs if t.get("transaction_type") == "expense")
    business_expense = sum(
        t["amount"]
        for t in txs
        if t.get("transaction_type") == "expense" and t.get("domain") == "business"
    )
    deductible = sum(
        (t["amount"] or 0) * (t.get("deduction_rate") or 1.0)
        for t in txs
        if t.get("is_deductible")
    )
    needs_review = sum(
        1 for t in txs if t.get("needs_review") or t.get("domain") == "unknown"
    )

    def _bucket(key_fn, type_filter=None):
        agg: dict[str, dict] = {}
        for t in txs:
            if type_filter and t.get("transaction_type") != type_filter:
                continue
            k = key_fn(t) or "Uncategorized"
            b = agg.setdefault(k, {"name": k, "total": 0.0, "count": 0})
            b["total"] += t.get("amount") or 0
            b["count"] += 1
        return sorted(agg.values(), key=lambda x: x["total"], reverse=True)

    # Monthly trend (income vs expense).
    months: dict[str, dict] = {}
    for t in txs:
        m = (t.get("email_date") or "")[:7]
        if not m:
            continue
        b = months.setdefault(m, {"month": m, "income": 0.0, "expense": 0.0})
        if t.get("transaction_type") == "income":
            b["income"] += t.get("amount") or 0
        elif t.get("transaction_type") == "expense":
            b["expense"] += t.get("amount") or 0

    return {
        "year": year,
        "totals": {
            "income": round(income, 2),
            "expense": round(expense, 2),
            "net": round(income - expense, 2),
            "business_expense": round(business_expense, 2),
            "deductible": round(deductible, 2),
            "transaction_count": len(txs),
            "needs_review": needs_review,
        },
        "by_category": _bucket(lambda t: t.get("category"), "expense")[:12],
        "by_merchant": _bucket(lambda t: t.get("merchant_name"), "expense")[:12],
        "by_domain": _bucket(lambda t: t.get("domain")),
        "monthly_trend": sorted(months.values(), key=lambda x: x["month"]),
    }


def update_transaction(composite_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    if ":" not in composite_id:
        raise ValueError("Invalid transaction id")
    stem, _, rowid = composite_id.partition(":")
    path = os.path.join(DB_DIR, f"{stem}.db")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ledger {stem} not found")

    safe = {k: v for k, v in changes.items() if k in EDITABLE_FIELDS}
    if not safe:
        raise ValueError("No editable fields supplied")

    # Coerce booleans to SQLite ints.
    for bool_field in ("is_deductible", "needs_review", "reviewed", "flagged"):
        if bool_field in safe:
            safe[bool_field] = 1 if safe[bool_field] else 0

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    set_clause += ", updated_at = datetime('now'), classification_method = 'manual'"
    with _connect(path) as conn:
        conn.execute(
            f"UPDATE transactions SET {set_clause} WHERE id = ?",
            list(safe.values()) + [int(rowid)],
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (int(rowid),)
        ).fetchone()
    if not row:
        raise FileNotFoundError("Transaction not found")
    return _row_to_tx(row, stem)


def list_categories() -> list[dict[str, Any]]:
    seen: dict[str, dict] = {}
    for path in _db_files():
        with _connect(path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
            ).fetchone()
            if not row:
                continue
            for r in conn.execute(
                "SELECT name, domain, tx_type, tax_relevant, irs_line FROM categories "
                "ORDER BY sort_order"
            ):
                seen[r["name"]] = dict(r)
    return list(seen.values())


def scan_history(limit: int = 25) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _db_files():
        with _connect(path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scan_history'"
            ).fetchone()
            if not row:
                continue
            for r in conn.execute(
                "SELECT * FROM scan_history ORDER BY started_at DESC LIMIT ?", (limit,)
            ):
                out.append(dict(r))
    out.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    return out[:limit]


def schedule_c(year: int) -> dict[str, Any]:
    """IRS Schedule C style aggregation for business transactions."""
    txs = list_transactions(year=year, domain="business", limit=1_000_000)

    income_lines: dict[str, dict] = {}
    expense_lines: dict[str, dict] = {}
    for t in txs:
        line = t.get("tax_category") or t.get("category") or "Uncategorized"
        target = income_lines if t.get("transaction_type") == "income" else expense_lines
        b = target.setdefault(line, {"line": line, "total": 0.0, "deductible": 0.0, "count": 0})
        amt = t.get("amount") or 0
        b["total"] += amt
        b["count"] += 1
        if t.get("transaction_type") == "expense":
            rate = t.get("deduction_rate") or (1.0 if t.get("is_deductible") else 0.0)
            b["deductible"] += amt * rate

    gross = sum(b["total"] for b in income_lines.values())
    total_deductible = sum(b["deductible"] for b in expense_lines.values())
    return {
        "year": year,
        "gross_income": round(gross, 2),
        "total_expenses": round(sum(b["total"] for b in expense_lines.values()), 2),
        "total_deductible": round(total_deductible, 2),
        "net_profit": round(gross - total_deductible, 2),
        "income": sorted(income_lines.values(), key=lambda x: x["total"], reverse=True),
        "expenses": sorted(expense_lines.values(), key=lambda x: x["deductible"], reverse=True),
    }
