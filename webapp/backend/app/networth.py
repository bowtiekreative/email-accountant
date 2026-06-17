"""Net-worth tracking: manually-tracked asset & liability accounts with balance
snapshots over time, a current summary, a history series, and a projection that
combines today's net worth with your monthly investable surplus."""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from . import invest
from .config import DB_DIR

_MAIN_DB = os.path.join(DB_DIR, "email_accountant.db")

ASSET_CATEGORIES = ["investment", "savings", "cash", "property", "crypto", "retirement", "other_asset"]
LIABILITY_CATEGORIES = ["credit_card", "loan", "mortgage", "student_loan", "other_debt"]


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_MAIN_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS networth_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('asset','liability')),
            category TEXT,
            currency TEXT DEFAULT 'USD',
            institution TEXT,
            created_at TEXT DEFAULT (datetime('now')))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS networth_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES networth_accounts(id) ON DELETE CASCADE,
            balance REAL NOT NULL,
            as_of TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')))"""
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Accounts + snapshots
# ---------------------------------------------------------------------------

def add_account(name: str, kind: str, category: str = "", currency: str = "USD",
                institution: str = "", balance: Optional[float] = None) -> dict[str, Any]:
    if kind not in ("asset", "liability"):
        raise ValueError("kind must be 'asset' or 'liability'")
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO networth_accounts (name, kind, category, currency, institution) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, kind, category, currency, institution),
    )
    account_id = cur.lastrowid
    if balance is not None:
        conn.execute(
            "INSERT INTO networth_snapshots (account_id, balance, as_of) VALUES (?, ?, ?)",
            (account_id, balance, datetime.now().date().isoformat()),
        )
    conn.commit()
    conn.close()
    return {"id": account_id, "name": name, "kind": kind}


def delete_account(account_id: int) -> None:
    conn = _conn()
    conn.execute("DELETE FROM networth_snapshots WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM networth_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()


def record_snapshot(account_id: int, balance: float, as_of: Optional[str] = None) -> dict[str, Any]:
    as_of = as_of or datetime.now().date().isoformat()
    conn = _conn()
    # One snapshot per account per day — update if it exists.
    existing = conn.execute(
        "SELECT id FROM networth_snapshots WHERE account_id = ? AND as_of = ?",
        (account_id, as_of),
    ).fetchone()
    if existing:
        conn.execute("UPDATE networth_snapshots SET balance = ? WHERE id = ?",
                     (balance, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO networth_snapshots (account_id, balance, as_of) VALUES (?, ?, ?)",
            (account_id, balance, as_of),
        )
    conn.commit()
    conn.close()
    return {"account_id": account_id, "balance": balance, "as_of": as_of}


def list_accounts() -> list[dict[str, Any]]:
    """Accounts with their most recent balance."""
    conn = _conn()
    accts = conn.execute("SELECT * FROM networth_accounts ORDER BY kind, category, name").fetchall()
    out = []
    for a in accts:
        latest = conn.execute(
            "SELECT balance, as_of FROM networth_snapshots WHERE account_id = ? "
            "ORDER BY as_of DESC, id DESC LIMIT 1",
            (a["id"],),
        ).fetchone()
        d = dict(a)
        d["balance"] = latest["balance"] if latest else 0.0
        d["as_of"] = latest["as_of"] if latest else None
        out.append(d)
    conn.close()
    return out


# ---------------------------------------------------------------------------
# Summary, history, projection
# ---------------------------------------------------------------------------

def summary(currency: str = "USD") -> dict[str, Any]:
    accts = [a for a in list_accounts() if a["currency"] == currency]
    assets = sum(a["balance"] for a in accts if a["kind"] == "asset")
    liabilities = sum(a["balance"] for a in accts if a["kind"] == "liability")

    by_category: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "kind": "asset"})
    for a in accts:
        key = a["category"] or a["kind"]
        by_category[key]["total"] += a["balance"]
        by_category[key]["kind"] = a["kind"]

    return {
        "currency": currency,
        "assets": round(assets, 2),
        "liabilities": round(liabilities, 2),
        "net_worth": round(assets - liabilities, 2),
        "by_category": [
            {"category": k, "total": round(v["total"], 2), "kind": v["kind"]}
            for k, v in sorted(by_category.items(), key=lambda kv: -kv[1]["total"])
        ],
        "accounts": accts,
    }


def history(currency: str = "USD") -> list[dict[str, Any]]:
    """Net worth at each month-end, using the latest snapshot per account up to
    that month (carried forward). Returns a monthly series for charting."""
    conn = _conn()
    accts = {a["id"]: a for a in conn.execute(
        "SELECT * FROM networth_accounts WHERE currency = ?", (currency,)
    ).fetchall()}
    if not accts:
        conn.close()
        return []
    snaps = conn.execute(
        "SELECT account_id, balance, as_of FROM networth_snapshots "
        "WHERE account_id IN (%s) ORDER BY as_of" % ",".join("?" * len(accts)),
        list(accts.keys()),
    ).fetchall()
    conn.close()
    if not snaps:
        return []

    months = sorted({s["as_of"][:7] for s in snaps})
    start, end = months[0], datetime.now().strftime("%Y-%m")
    # Build the full month range.
    all_months = []
    y, m = int(start[:4]), int(start[5:7])
    while f"{y:04d}-{m:02d}" <= end:
        all_months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1

    series = []
    for month in all_months:
        latest: dict[int, tuple[str, float]] = {}
        for s in snaps:
            if s["as_of"][:7] <= month:
                latest[s["account_id"]] = (s["as_of"], s["balance"])
        assets = sum(b for aid, (_, b) in latest.items() if accts[aid]["kind"] == "asset")
        liab = sum(b for aid, (_, b) in latest.items() if accts[aid]["kind"] == "liability")
        series.append({"month": month, "net_worth": round(assets - liab, 2)})
    return series


def projection(currency: str = "USD", annual_rate: float = 0.07, years: int = 30) -> dict[str, Any]:
    """Project net worth forward from today's value + your monthly surplus,
    compounded at the given rate. Surplus comes from the last 12 months."""
    current = summary(currency)["net_worth"]
    cash = invest._cashflow(currency)
    monthly = max(0.0, cash["monthly_surplus"])

    growth = invest.compound_growth(
        principal=current, monthly_contribution=monthly,
        annual_rate=annual_rate, years=years,
    )
    return {
        "currency": currency,
        "starting_net_worth": round(current, 2),
        "monthly_surplus_invested": round(monthly, 2),
        "annual_rate": annual_rate,
        "years": years,
        "future_value": growth["future_value"],
        "series": growth["series"],
        "note": (
            "Projects today's net worth plus your average monthly surplus, "
            f"invested at {annual_rate*100:.0f}%/yr. A guide, not a guarantee."
        ),
    }
