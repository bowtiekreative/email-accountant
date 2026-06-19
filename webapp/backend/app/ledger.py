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
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import DB_DIR, START_YEAR

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
    "txn_state",
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


def _ensure_state(conn: sqlite3.Connection) -> None:
    """Add the txn_state column to older ledgers that predate it."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
    if "txn_state" not in cols:
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN txn_state TEXT DEFAULT 'paid'")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def _account_map(conn: sqlite3.Connection) -> dict[int, str]:
    """Map account_id -> label for a ledger DB (for per-account filtering)."""
    has = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='email_accounts'"
    ).fetchone()
    if not has:
        return {}
    return {r["id"]: r["label"] for r in conn.execute("SELECT id, label FROM email_accounts")}


def available_accounts() -> list[str]:
    """Distinct account labels that appear across all ledgers."""
    labels: set[str] = set()
    for path in _db_files():
        with _connect(path) as conn:
            labels.update(_account_map(conn).values())
    return sorted(labels)


def available_years() -> list[int]:
    """Every tax year from START_YEAR to the current year, plus any years that
    actually have data (in case the ledger contains older or future emails).
    This guarantees all tax years from 2006 onward are always selectable."""
    current = datetime.now().year
    years: set[int] = set(range(START_YEAR, current + 1))
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
    # Normalize currency so CAD/USD grouping is reliable.
    d["currency"] = (d.get("currency") or "USD").upper()
    return d


def available_currencies() -> list[str]:
    """Distinct currencies present across all ledgers (CAD/USD first)."""
    txs = list_transactions(limit=1_000_000)
    found = {t["currency"] for t in txs}
    ordered = [c for c in ("USD", "CAD") if c in found]
    ordered += sorted(found - set(ordered))
    return ordered or ["USD"]


def list_transactions(
    year: Optional[int] = None,
    domain: Optional[str] = None,
    tx_type: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    needs_review: Optional[bool] = None,
    currency: Optional[str] = None,
    account: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []
    if year:
        where.append("substr(email_date,1,4) = ?")
        params.append(str(year))
    if currency:
        where.append("COALESCE(NULLIF(currency,''), 'USD') = ?")
        params.append(currency)
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
    if state:
        where.append("COALESCE(txn_state,'paid') = ?")
        params.append(state)

    clause = " AND ".join(where)
    results: list[dict[str, Any]] = []
    for path in _db_files():
        with _connect(path) as conn:
            if not _has_transactions_table(conn):
                continue
            _ensure_state(conn)
            stem = _stem(path)
            acct_map = _account_map(conn)
            rows = conn.execute(
                f"SELECT * FROM transactions WHERE {clause} ORDER BY email_date DESC",
                params,
            ).fetchall()
            for r in rows:
                tx = _row_to_tx(r, stem)
                tx["account"] = acct_map.get(tx.get("account_id"))
                results.append(tx)

    if account:
        results = [t for t in results if t.get("account") == account]

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


def _totals(txs: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "net": round(income - expense, 2),
        "business_expense": round(business_expense, 2),
        "deductible": round(deductible, 2),
        "transaction_count": len(txs),
    }


def overview(year: Optional[int] = None, currency: Optional[str] = None,
             account: Optional[str] = None) -> dict[str, Any]:
    """Aggregate dashboard numbers across all ledgers for a year (or all).

    CAD and USD are kept separate (no FX conversion). ``totals_by_currency``
    always lists every currency; the category/merchant/trend breakdowns use the
    selected ``currency`` (or the most common one when none is given).
    """
    all_txs = list_transactions(year=year, account=account, limit=1_000_000)
    currencies = available_currencies()

    totals_by_currency = {
        cur: _totals([t for t in all_txs if t["currency"] == cur]) for cur in currencies
    }

    needs_review = sum(
        1 for t in all_txs if t.get("needs_review") or t.get("domain") == "unknown"
    )

    # Pick the active currency for the breakdowns.
    if currency and currency in currencies:
        active = currency
    else:
        active = max(
            currencies,
            key=lambda c: totals_by_currency[c]["transaction_count"],
            default="USD",
        )
    txs = [t for t in all_txs if t["currency"] == active]

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
        "currencies": currencies,
        "active_currency": active,
        "totals_by_currency": totals_by_currency,
        "needs_review": needs_review,
        "by_category": _bucket(lambda t: t.get("category"), "expense")[:12],
        "by_merchant": _bucket(lambda t: t.get("merchant_name"), "expense")[:12],
        "by_domain": _bucket(lambda t: t.get("domain")),
        "monthly_trend": sorted(months.values(), key=lambda x: x["month"]),
    }


def update_transaction(
    composite_id: str, changes: dict[str, Any], learn: bool = True
) -> dict[str, Any]:
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

    result = _row_to_tx(row, stem)

    # Learn from a classification correction: save a merchant rule and apply it
    # to past transactions from the same merchant.
    learned = None
    if learn and any(k in safe for k in ("domain", "transaction_type", "category")):
        merchant = row["merchant_name"]
        if merchant:
            from . import learning
            learned = learning.learn_from_edit(merchant, safe, exclude_id=int(rowid))
    result["_learned"] = learned
    return result


def count_transactions(**filters: Any) -> int:
    """Total transactions matching the same filters as list_transactions."""
    return len(list_transactions(limit=10_000_000, **filters))


def delete_transactions(composite_ids: list[str]) -> int:
    """Delete specific transactions by composite id (grouped per ledger file)."""
    by_stem: dict[str, list[int]] = {}
    for cid in composite_ids:
        if ":" in cid:
            stem, _, rowid = cid.partition(":")
            by_stem.setdefault(stem, []).append(int(rowid))
    total = 0
    for stem, ids in by_stem.items():
        path = os.path.join(DB_DIR, f"{stem}.db")
        if not os.path.exists(path):
            continue
        with _connect(path) as conn:
            ph = ",".join("?" * len(ids))
            cur = conn.execute(f"DELETE FROM transactions WHERE id IN ({ph})", ids)
            total += cur.rowcount
            conn.commit()
    return total


def clear_all() -> dict[str, int]:
    """Wipe all transactions, emails, attachments and receipts — a clean restart."""
    counts = {"transactions": 0, "emails": 0}
    for path in _db_files():
        with _connect(path) as conn:
            for table in ("transactions", "extracted_receipts", "attachments",
                          "pipeline_logs", "monthly_summaries", "emails"):
                try:
                    cur = conn.execute(f"DELETE FROM {table}")
                    if table in counts:
                        counts[table] += cur.rowcount
                except sqlite3.OperationalError:
                    pass
            conn.commit()
    return counts


def transaction_detail(composite_id: str) -> dict[str, Any]:
    """Full transaction + the source email (subject, body, html) + attachments."""
    if ":" not in composite_id:
        raise ValueError("Invalid transaction id")
    stem, _, rowid = composite_id.partition(":")
    path = os.path.join(DB_DIR, f"{stem}.db")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ledger {stem} not found")
    with _connect(path) as conn:
        _ensure_state(conn)
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (int(rowid),)).fetchone()
        if not row:
            raise FileNotFoundError("Transaction not found")
        tx = _row_to_tx(row, stem)
        tx["account"] = _account_map(conn).get(tx.get("account_id"))
        email = None
        if tx.get("email_id"):
            er = conn.execute("SELECT * FROM emails WHERE id = ?", (tx["email_id"],)).fetchone()
            if er:
                email = dict(er)
        attachments = []
        if tx.get("email_id"):
            for a in conn.execute(
                "SELECT filename, mime_type, filepath, ocr_text FROM attachments WHERE email_id = ?",
                (tx["email_id"],),
            ):
                attachments.append(dict(a))
    return {"transaction": tx, "email": email, "attachments": attachments}


def reprocess_all(limit: int = 10_000_000) -> dict[str, Any]:
    """Re-run classification + state detection over every stored transaction.

    Uses the denormalized merchant/subject on each row, so it works without the
    original email. Skips rows you've reviewed manually. Run this after adding
    new categories/merchant rules so all (20k+) transactions are re-read.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from pipeline.processor import classify_merchant, detect_state, load_learned_rules
    load_learned_rules(force=True)

    changed = 0
    scanned = 0
    for path in _db_files():
        with _connect(path) as conn:
            if not _has_transactions_table(conn):
                continue
            _ensure_state(conn)
            rows = conn.execute(
                "SELECT id, merchant_name, email_subject, email_from, amount, reviewed "
                "FROM transactions LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                scanned += 1
                if r["reviewed"]:
                    continue
                merchant = r["merchant_name"] or r["email_from"] or ""
                subject = r["email_subject"] or ""
                domain, tx_type, category, conf = classify_merchant(
                    merchant, subject, r["amount"] or 0, r["email_from"] or ""
                )
                state = detect_state(subject, "", category)
                conn.execute(
                    "UPDATE transactions SET domain=?, transaction_type=?, category=?, "
                    "txn_state=?, classification_confidence=?, classification_method='reprocess', "
                    "needs_review=? , updated_at=datetime('now') WHERE id=?",
                    (domain, tx_type, category, state, round(conf, 3),
                     1 if conf < 0.5 else 0, r["id"]),
                )
                changed += 1
            conn.commit()
    return {"scanned": scanned, "updated": changed}


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


# ---------------------------------------------------------------------------
# Tax category mappings
# ---------------------------------------------------------------------------

# App category -> CRA T2125 expense line (Part 4). Used when a transaction has
# no explicit tax_category. Meals carry the standard 50% limit.
T2125_EXPENSE_LINES = {
    "Marketing & Advertising": "8521 Advertising",
    "Online Ads": "8521 Advertising",
    "Charitable Sponsorship": "8521 Advertising",
    "Travel & Meals": "8523 Meals and entertainment (50%)",
    "Meals & Entertainment": "8523 Meals and entertainment (50%)",
    "Dining Out": "8523 Meals and entertainment (50%)",
    "Business Insurance": "8690 Insurance",
    "Interest & Bank Fees": "8710 Interest and bank charges",
    "Merchant & Processing Fees": "8710 Interest and bank charges",
    "Banking Fees": "8710 Interest and bank charges",
    "Licenses & Permits": "8760 Business taxes, licences, memberships",
    "Dues & Memberships": "8760 Business taxes, licences, memberships",
    "Taxes & Fees (Business)": "8760 Business taxes, licences, memberships",
    "Office Supplies": "8811 Office stationery and supplies",
    "Materials & Supplies": "8811 Office stationery and supplies",
    "Software & Subscriptions": "8810 Office expenses",
    "Web Hosting & Domains": "8810 Office expenses",
    "Equipment & Hardware": "8810 Office expenses",
    "Professional Services": "8860 Professional fees",
    "Contractors & Freelancers": "8360 Subcontracts",
    "Wages & Payroll": "9060 Salaries, wages, benefits",
    "Employee Benefits": "9060 Salaries, wages, benefits",
    "Office Rent": "8910 Rent",
    "Housing & Rent": "8910 Rent",
    "Repairs & Maintenance": "8960 Repairs and maintenance",
    "Business Travel": "9200 Travel",
    "Internet & Telecom": "9220 Telephone and utilities",
    "Utilities (Business)": "9220 Telephone and utilities",
    "Vehicle & Auto": "9281 Motor vehicle expenses",
    "Fuel & Gas (Business)": "9224 Fuel costs",
    "Shipping & Postage": "9275 Delivery, freight and express",
    "Inventory & COGS": "8320 Cost of goods sold (purchases)",
    "Depreciation": "9936 Capital cost allowance (CCA)",
    "Home Office": "9945 Business-use-of-home expenses",
    "Education & Training": "9270 Other expenses",
    "Other Business Expense": "9270 Other expenses",
}
T2125_INCOME_LINE = "8000 Sales / business income"

# App category -> IRS Schedule C expense line. Used when a transaction has no
# explicit tax_category.
SCHEDULE_C_EXPENSE_LINES = {
    "Marketing & Advertising": "Line 8 Advertising",
    "Online Ads": "Line 8 Advertising",
    "Charitable Sponsorship": "Line 8 Advertising",
    "Vehicle & Auto": "Line 9 Car and truck expenses",
    "Fuel & Gas (Business)": "Line 9 Car and truck expenses",
    "Merchant & Processing Fees": "Line 10 Commissions and fees",
    "Contractors & Freelancers": "Line 11 Contract labor",
    "Equipment & Hardware": "Line 13 Depreciation (Section 179)",
    "Depreciation": "Line 13 Depreciation",
    "Employee Benefits": "Line 14 Employee benefit programs",
    "Business Insurance": "Line 15 Insurance",
    "Interest & Bank Fees": "Line 16b Interest (other)",
    "Banking Fees": "Line 16b Interest (other)",
    "Professional Services": "Line 17 Legal and professional services",
    "Office Supplies": "Line 18 Office expense",
    "Software & Subscriptions": "Line 18 Office expense",
    "Office Rent": "Line 20b Rent (other business property)",
    "Repairs & Maintenance": "Line 21 Repairs and maintenance",
    "Materials & Supplies": "Line 22 Supplies",
    "Licenses & Permits": "Line 23 Taxes and licenses",
    "Taxes & Fees (Business)": "Line 23 Taxes and licenses",
    "Dues & Memberships": "Line 23 Taxes and licenses",
    "Business Travel": "Line 24a Travel",
    "Travel & Meals": "Line 24b Meals (50%)",
    "Meals & Entertainment": "Line 24b Meals (50%)",
    "Dining Out": "Line 24b Meals (50%)",
    "Internet & Telecom": "Line 25 Utilities",
    "Utilities (Business)": "Line 25 Utilities",
    "Wages & Payroll": "Line 26 Wages",
    "Web Hosting & Domains": "Line 27a Other expenses",
    "Shipping & Postage": "Line 27a Other expenses",
    "Education & Training": "Line 27a Other expenses",
    "Inventory & COGS": "Line 4 Cost of goods sold",
    "Home Office": "Line 30 Home office",
    "Other Business Expense": "Line 27a Other expenses",
}


def _line_aggregate(
    txs: list[dict[str, Any]],
    expense_line_fn,
    income_line: str,
) -> dict[str, Any]:
    income_lines: dict[str, dict] = {}
    expense_lines: dict[str, dict] = {}
    for t in txs:
        amt = t.get("amount") or 0
        if t.get("transaction_type") == "income":
            b = income_lines.setdefault(
                income_line, {"line": income_line, "total": 0.0, "deductible": 0.0, "count": 0}
            )
            b["total"] += amt
            b["count"] += 1
        else:
            line = expense_line_fn(t)
            b = expense_lines.setdefault(
                line, {"line": line, "total": 0.0, "deductible": 0.0, "count": 0}
            )
            b["total"] += amt
            b["count"] += 1
            rate = t.get("deduction_rate") or (1.0 if t.get("is_deductible") else 0.0)
            b["deductible"] += amt * rate

    gross = sum(b["total"] for b in income_lines.values())
    total_deductible = sum(b["deductible"] for b in expense_lines.values())
    return {
        "gross_income": round(gross, 2),
        "total_expenses": round(sum(b["total"] for b in expense_lines.values()), 2),
        "total_deductible": round(total_deductible, 2),
        "net_profit": round(gross - total_deductible, 2),
        "income": sorted(income_lines.values(), key=lambda x: x["total"], reverse=True),
        "expenses": sorted(expense_lines.values(), key=lambda x: x["deductible"], reverse=True),
    }


def schedule_c(year: int, currency: str = "USD") -> dict[str, Any]:
    """IRS Schedule C (US) aggregation for business transactions."""
    txs = list_transactions(
        year=year, domain="business", currency=currency, limit=1_000_000
    )

    def _line(t: dict[str, Any]) -> str:
        # Prefer an explicit IRS tax_category; otherwise map from the category.
        explicit = t.get("tax_category")
        if explicit and explicit.lower().startswith("line"):
            return explicit
        cat = t.get("category") or ""
        return SCHEDULE_C_EXPENSE_LINES.get(cat, "Line 27a Other expenses")

    agg = _line_aggregate(
        txs, _line, income_line="Gross receipts (Line 1)"
    )
    return {"year": year, "currency": currency, "form": "US Schedule C", **agg}


def t2125(year: int, currency: str = "CAD") -> dict[str, Any]:
    """CRA T2125 (Canada) aggregation for business transactions."""
    txs = list_transactions(
        year=year, domain="business", currency=currency, limit=1_000_000
    )

    def _line(t: dict[str, Any]) -> str:
        cat = t.get("category") or ""
        return T2125_EXPENSE_LINES.get(cat, "9270 Other expenses")

    agg = _line_aggregate(txs, _line, income_line=T2125_INCOME_LINE)
    return {"year": year, "currency": currency, "form": "CRA T2125", **agg}


def gst_hst(year: int, currency: str = "CAD") -> dict[str, Any]:
    """GST/HST summary for Canadian business activity.

    GST/HST you may have *collected* on sales, and input tax credits (ITCs) on
    expenses. Where a linked receipt recorded an explicit tax amount we use it;
    otherwise the tax portion is shown as unknown so nothing is invented.
    """
    txs = list_transactions(
        year=year, domain="business", currency=currency, limit=1_000_000
    )

    sales = sum(t["amount"] for t in txs if t.get("transaction_type") == "income")
    sales_count = sum(1 for t in txs if t.get("transaction_type") == "income")
    expenses = sum(t["amount"] for t in txs if t.get("transaction_type") == "expense")
    expense_count = sum(1 for t in txs if t.get("transaction_type") == "expense")

    return {
        "year": year,
        "currency": currency,
        "taxable_sales": round(sales, 2),
        "sales_count": sales_count,
        "eligible_expenses": round(expenses, 2),
        "expense_count": expense_count,
        # Explicit tax amounts are not yet captured per-transaction in the
        # ledger, so we surface the bases and let the user apply their rate.
        "note": (
            "GST/HST collected and input tax credits depend on the exact tax "
            "portion of each transaction, which the pipeline does not yet store "
            "separately. These are the taxable bases — apply your registered "
            "rate (e.g. 5% GST or your provincial HST) at filing time."
        ),
    }
