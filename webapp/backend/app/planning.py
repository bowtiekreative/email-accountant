"""Budgeting + planning suite: subscription detection, budget recommendations,
budget CRUD, and a yearly plan. All currency-aware (CAD/USD never mixed)."""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any, Optional

from . import ledger
from .config import DB_DIR

# Budgets live in the year-less main ledger so there's a single source of truth.
_MAIN_DB = os.path.join(DB_DIR, "email_accountant.db")


def _main_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_MAIN_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER, category TEXT NOT NULL,
            monthly_limit REAL NOT NULL, annual_limit REAL,
            domain TEXT, currency TEXT DEFAULT 'USD', is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')))"""
    )
    # Older schemas may lack the currency column; add it if missing.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(budgets)")}
    if "currency" not in cols:
        conn.execute("ALTER TABLE budgets ADD COLUMN currency TEXT DEFAULT 'USD'")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def _interval_label(days: float) -> tuple[str, float]:
    """Map an average gap in days to (frequency, times-per-year)."""
    if days <= 10:
        return "weekly", 52.0
    if days <= 45:
        return "monthly", 12.0
    if days <= 100:
        return "quarterly", 4.0
    return "yearly", 1.0


def subscriptions(currency: Optional[str] = None) -> dict[str, Any]:
    """Detect recurring charges (subscriptions) from the ledger.

    A merchant is treated as a subscription when it has >=3 expense charges of
    similar amount at a roughly regular cadence.
    """
    txs = [
        t for t in ledger.list_transactions(currency=currency, limit=1_000_000)
        if t.get("transaction_type") == "expense" and t.get("merchant_name")
    ]

    by_merchant: dict[tuple, list] = defaultdict(list)
    for t in txs:
        key = ((t.get("merchant_name") or "").strip().lower(), t["currency"])
        if t.get("email_date"):
            by_merchant[key].append(t)

    subs = []
    now = datetime.now()
    for (merchant, cur), items in by_merchant.items():
        if len(items) < 3:
            continue
        items.sort(key=lambda x: x.get("email_date") or "")
        dates = []
        for it in items:
            try:
                dates.append(datetime.fromisoformat((it["email_date"])[:19]))
            except (ValueError, TypeError):
                pass
        if len(dates) < 3:
            continue
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        amounts = [it.get("amount") or 0 for it in items]
        typical = median(amounts)
        # Require amount consistency (median-ish charges).
        consistent = sum(1 for a in amounts if abs(a - typical) <= max(2.0, typical * 0.25))
        if consistent < max(3, len(amounts) // 2):
            continue

        freq, per_year = _interval_label(avg_gap)
        last_date = dates[-1]
        days_since = (now - last_date).days
        active = days_since <= avg_gap * 1.8
        monthly_cost = typical * per_year / 12.0

        subs.append({
            "merchant": items[-1].get("merchant_name"),
            "currency": cur,
            "category": items[-1].get("category"),
            "domain": items[-1].get("domain"),
            "frequency": freq,
            "typical_amount": round(typical, 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(typical * per_year, 2),
            "charges": len(items),
            "last_charge": last_date.date().isoformat(),
            "active": active,
        })

    subs.sort(key=lambda s: (not s["active"], -s["monthly_cost"]))

    # Monthly burn rate per currency (active only).
    burn: dict[str, float] = defaultdict(float)
    for s in subs:
        if s["active"]:
            burn[s["currency"]] += s["monthly_cost"]

    return {
        "subscriptions": subs,
        "monthly_burn_by_currency": {k: round(v, 2) for k, v in burn.items()},
        "active_count": sum(1 for s in subs if s["active"]),
    }


# ---------------------------------------------------------------------------
# Budgets + recommendations
# ---------------------------------------------------------------------------

def list_budgets() -> list[dict[str, Any]]:
    conn = _main_conn()
    rows = conn.execute("SELECT * FROM budgets WHERE is_active = 1 ORDER BY category").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_budget(category: str, monthly_limit: float, currency: str = "USD",
               domain: Optional[str] = None) -> dict[str, Any]:
    conn = _main_conn()
    existing = conn.execute(
        "SELECT id FROM budgets WHERE category = ? AND currency = ?",
        (category, currency),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE budgets SET monthly_limit=?, annual_limit=?, domain=?, "
            "is_active=1, updated_at=datetime('now') WHERE id=?",
            (monthly_limit, monthly_limit * 12, domain, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO budgets (category, monthly_limit, annual_limit, domain, currency) "
            "VALUES (?, ?, ?, ?, ?)",
            (category, monthly_limit, monthly_limit * 12, domain, currency),
        )
    conn.commit()
    conn.close()
    return {"category": category, "monthly_limit": monthly_limit, "currency": currency}


def delete_budget(category: str, currency: str = "USD") -> None:
    conn = _main_conn()
    conn.execute(
        "UPDATE budgets SET is_active=0 WHERE category=? AND currency=?",
        (category, currency),
    )
    conn.commit()
    conn.close()


def _monthly_category_spend(currency: str, months_back: int = 12) -> dict[str, dict]:
    """Average monthly spend per expense category over the trailing window."""
    txs = [
        t for t in ledger.list_transactions(currency=currency, limit=1_000_000)
        if t.get("transaction_type") == "expense"
    ]
    cutoff = datetime.now().replace(day=1)
    # Trailing window start (approx).
    start_year = cutoff.year - (months_back // 12)
    start_month = cutoff.month - (months_back % 12)
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    start = f"{start_year:04d}-{start_month:02d}"

    cat_months: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in txs:
        m = (t.get("email_date") or "")[:7]
        if not m or m < start:
            continue
        cat = t.get("category") or "Uncategorized"
        cat_months[cat][m] += t.get("amount") or 0

    out = {}
    for cat, months in cat_months.items():
        vals = list(months.values())
        total = sum(vals)
        n_months = max(1, len(months))
        out[cat] = {
            "avg_monthly": round(total / months_back, 2),
            "peak_monthly": round(max(vals), 2) if vals else 0.0,
            "active_months": n_months,
            "total": round(total, 2),
        }
    return out


def budget_recommendations(currency: str = "USD") -> dict[str, Any]:
    """Recommend a monthly budget per category from trailing-12-month history.

    Recommendation = round up the average monthly spend with ~10% headroom,
    capped at the observed peak so it stays realistic.
    """
    spend = _monthly_category_spend(currency)
    current = {b["category"]: b for b in list_budgets() if b.get("currency") == currency}

    recs = []
    for cat, s in sorted(spend.items(), key=lambda kv: kv[1]["avg_monthly"], reverse=True):
        if s["avg_monthly"] <= 0:
            continue
        rec = min(s["peak_monthly"], s["avg_monthly"] * 1.1)
        rec = max(rec, s["avg_monthly"])  # never below the average
        # Round to a tidy number.
        rec = float(round(rec / 5) * 5) if rec >= 20 else round(rec, 2)
        existing = current.get(cat)
        recs.append({
            "category": cat,
            "currency": currency,
            "avg_monthly": s["avg_monthly"],
            "peak_monthly": s["peak_monthly"],
            "recommended_monthly": rec,
            "current_budget": existing["monthly_limit"] if existing else None,
            "status": (
                "no budget" if not existing
                else "over" if existing["monthly_limit"] < s["avg_monthly"]
                else "ok"
            ),
        })
    return {"currency": currency, "recommendations": recs}


def apply_recommended_budgets(currency: str = "USD") -> dict[str, Any]:
    """Set every recommended budget that doesn't already exist."""
    recs = budget_recommendations(currency)["recommendations"]
    applied = 0
    for r in recs:
        if r["current_budget"] is None:
            set_budget(r["category"], r["recommended_monthly"], currency)
            applied += 1
    return {"applied": applied, "currency": currency}


# ---------------------------------------------------------------------------
# Yearly plan
# ---------------------------------------------------------------------------

def yearly_plan(year: int, currency: str = "USD") -> dict[str, Any]:
    """Project the year's income/expense and savings from data so far + budgets."""
    txs = [t for t in ledger.list_transactions(year=year, currency=currency, limit=1_000_000)]
    income = sum(t["amount"] for t in txs if t.get("transaction_type") == "income")
    expense = sum(t["amount"] for t in txs if t.get("transaction_type") == "expense")

    now = datetime.now()
    months_elapsed = now.month if year == now.year else 12
    months_elapsed = max(1, months_elapsed)
    frac = months_elapsed / 12.0

    projected_income = income / frac if year == now.year else income
    projected_expense = expense / frac if year == now.year else expense

    budgets = [b for b in list_budgets() if b.get("currency") == currency]
    budgeted_annual = sum((b.get("annual_limit") or b["monthly_limit"] * 12) for b in budgets)

    # Per-category actual vs budget for the year.
    by_cat: dict[str, float] = defaultdict(float)
    for t in txs:
        if t.get("transaction_type") == "expense":
            by_cat[t.get("category") or "Uncategorized"] += t.get("amount") or 0
    cat_status = []
    bmap = {b["category"]: b for b in budgets}
    for cat, spent in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True):
        b = bmap.get(cat)
        annual_budget = (b.get("annual_limit") or b["monthly_limit"] * 12) if b else None
        cat_status.append({
            "category": cat,
            "spent": round(spent, 2),
            "annual_budget": round(annual_budget, 2) if annual_budget else None,
            "over": bool(annual_budget and spent > annual_budget),
        })

    return {
        "year": year,
        "currency": currency,
        "months_elapsed": months_elapsed,
        "actual_income": round(income, 2),
        "actual_expense": round(expense, 2),
        "actual_net": round(income - expense, 2),
        "projected_income": round(projected_income, 2),
        "projected_expense": round(projected_expense, 2),
        "projected_net": round(projected_income - projected_expense, 2),
        "budgeted_annual_expense": round(budgeted_annual, 2),
        "categories": cat_status,
    }
