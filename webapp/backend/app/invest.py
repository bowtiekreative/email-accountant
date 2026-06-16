"""Wealth-building suite: investment calculators + personalized, Buffett-style
advice derived from the user's actual cashflow.

Educational only — not licensed financial advice. Default assumptions are
conservative long-run index-fund figures the user can change.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from . import ledger, planning

# Spending that's typically discretionary — the easiest dollars to redirect.
DISCRETIONARY = {
    "Dining Out", "Coffee Shops", "Food Delivery", "Entertainment", "Gaming",
    "Streaming & Subscriptions", "Shopping", "Alcohol & Bars", "Hobbies",
    "Social Media", "Books & Media",
}

DEFAULT_RETURN = 0.08          # long-run stock-market average (nominal)
SAFE_WITHDRAWAL = 0.04         # the "4% rule" for financial independence


# ---------------------------------------------------------------------------
# Calculators
# ---------------------------------------------------------------------------

def compound_growth(principal: float, monthly_contribution: float,
                    annual_rate: float = DEFAULT_RETURN, years: int = 20) -> dict[str, Any]:
    """Future value of a lump sum + regular monthly investing."""
    r = annual_rate / 12.0
    n = max(0, int(years * 12))
    balance = principal
    series = []
    contributed = principal
    for month in range(1, n + 1):
        balance = balance * (1 + r) + monthly_contribution
        contributed += monthly_contribution
        if month % 12 == 0:
            series.append({
                "year": month // 12,
                "balance": round(balance, 2),
                "contributed": round(contributed, 2),
                "growth": round(balance - contributed, 2),
            })
    return {
        "principal": round(principal, 2),
        "monthly_contribution": round(monthly_contribution, 2),
        "annual_rate": annual_rate,
        "years": years,
        "future_value": round(balance, 2),
        "total_contributed": round(contributed, 2),
        "total_growth": round(balance - contributed, 2),
        "series": series,
    }


def years_to_target(target: float, principal: float, monthly_contribution: float,
                    annual_rate: float = DEFAULT_RETURN) -> Optional[float]:
    """How long to reach a target balance. None if unreachable in 100 years."""
    if target <= principal:
        return 0.0
    r = annual_rate / 12.0
    balance = principal
    for month in range(1, 100 * 12 + 1):
        balance = balance * (1 + r) + monthly_contribution
        if balance >= target:
            return round(month / 12.0, 1)
    return None


def fire_number(annual_expense: float, withdrawal_rate: float = SAFE_WITHDRAWAL) -> dict[str, Any]:
    """Financial-independence target: the portfolio that funds your spending."""
    target = annual_expense / withdrawal_rate if withdrawal_rate else 0
    return {
        "annual_expense": round(annual_expense, 2),
        "withdrawal_rate": withdrawal_rate,
        "fire_number": round(target, 2),
        "note": f"At a {withdrawal_rate*100:.0f}% withdrawal rate, this portfolio "
                f"could cover {annual_expense:,.0f}/yr of spending.",
    }


# ---------------------------------------------------------------------------
# Cashflow snapshot (trailing 12 months, per currency)
# ---------------------------------------------------------------------------

def _cashflow(currency: str, months: int = 12) -> dict[str, Any]:
    txs = ledger.list_transactions(currency=currency, limit=1_000_000)
    now = datetime.now()
    start = f"{now.year - 1:04d}-{now.month:02d}"

    income = expense = 0.0
    disc = 0.0
    by_cat: dict[str, float] = defaultdict(float)
    seen_months: set[str] = set()
    for t in txs:
        m = (t.get("email_date") or "")[:7]
        if not m or m < start:
            continue
        seen_months.add(m)
        amt = t.get("amount") or 0
        if t.get("transaction_type") == "income":
            income += amt
        elif t.get("transaction_type") == "expense":
            expense += amt
            cat = t.get("category") or "Uncategorized"
            by_cat[cat] += amt
            if cat in DISCRETIONARY:
                disc += amt

    n = max(1, len(seen_months))
    top_disc = sorted(
        ((c, v) for c, v in by_cat.items() if c in DISCRETIONARY),
        key=lambda kv: kv[1], reverse=True,
    )[:5]
    return {
        "months": n,
        "monthly_income": round(income / n, 2),
        "monthly_expense": round(expense / n, 2),
        "monthly_surplus": round((income - expense) / n, 2),
        "monthly_discretionary": round(disc / n, 2),
        "top_discretionary": [
            {"category": c, "monthly": round(v / n, 2)} for c, v in top_disc
        ],
        "annual_expense": round(expense / n * 12, 2),
    }


# ---------------------------------------------------------------------------
# Advice engine
# ---------------------------------------------------------------------------

def wealth_advice(currency: str = "USD") -> dict[str, Any]:
    """Personalized, plain-English advice + projections from real cashflow."""
    cf = _cashflow(currency)
    subs = planning.subscriptions(currency=currency)
    inactive = [s for s in subs["subscriptions"] if not s["active"]]
    inactive_monthly = round(sum(s["monthly_cost"] for s in inactive), 2)
    active_burn = subs["monthly_burn_by_currency"].get(currency, 0.0)

    surplus = cf["monthly_surplus"]
    income = cf["monthly_income"]
    tips: list[dict[str, Any]] = []

    # 1. Pay yourself first.
    target_invest = round(max(0.0, income * 0.15), 2)
    if income > 0:
        tips.append({
            "title": "Pay yourself first",
            "severity": "high",
            "body": (
                f"Aim to invest ~15% of income — about {target_invest:,.0f} {currency}/mo. "
                "Automate it on payday so it happens before you can spend it."
            ),
        })

    # 2. Invest your surplus.
    if surplus > 0:
        proj = compound_growth(0, surplus, DEFAULT_RETURN, 20)
        tips.append({
            "title": "Put your surplus to work",
            "severity": "high",
            "body": (
                f"You're running a surplus of ~{surplus:,.0f} {currency}/mo. Invested at "
                f"{DEFAULT_RETURN*100:.0f}%/yr, that becomes "
                f"~{proj['future_value']:,.0f} {currency} in 20 years "
                f"({proj['total_growth']:,.0f} of it pure growth)."
            ),
        })
    elif income > 0:
        tips.append({
            "title": "Close the gap first",
            "severity": "high",
            "body": (
                "Your spending currently meets or exceeds income. Free up cashflow "
                "before investing — start with the discretionary categories below."
            ),
        })

    # 3. Cut inactive subscriptions.
    if inactive_monthly > 0:
        proj = compound_growth(0, inactive_monthly, DEFAULT_RETURN, 20)
        tips.append({
            "title": "Cancel zombie subscriptions",
            "severity": "medium",
            "body": (
                f"{len(inactive)} inactive subscription(s) ≈ {inactive_monthly:,.0f} "
                f"{currency}/mo. Redirected to investing, that's "
                f"~{proj['future_value']:,.0f} {currency} in 20 years."
            ),
        })

    # 4. Trim the biggest discretionary leak.
    if cf["top_discretionary"]:
        top = cf["top_discretionary"][0]
        half = round(top["monthly"] / 2, 2)
        if half > 0:
            proj = compound_growth(0, half, DEFAULT_RETURN, 20)
            tips.append({
                "title": f"Redirect half your {top['category']} spend",
                "severity": "medium",
                "body": (
                    f"You spend ~{top['monthly']:,.0f} {currency}/mo on {top['category']}. "
                    f"Investing half ({half:,.0f}/mo) grows to ~{proj['future_value']:,.0f} "
                    f"{currency} over 20 years."
                ),
            })

    # 5. Emergency fund (Buffett rule #1: don't lose money).
    ef_target = round(cf["monthly_expense"] * 6, 2)
    tips.append({
        "title": "Build a 6-month safety net",
        "severity": "medium",
        "body": (
            f"Keep ~{ef_target:,.0f} {currency} (6 months of expenses) in cash before "
            "investing aggressively, so you never have to sell investments at a bad time."
        ),
    })

    # 6. Buffett principles (always shown, educational).
    principles = [
        "Live below your means and invest the difference — consistently.",
        "Favor low-cost, broad index funds; let compounding do the work over decades.",
        "Don't try to time the market; time in the market beats timing the market.",
        "Avoid lifestyle inflation — when income rises, raise your savings rate first.",
        "Only invest money you won't need for 5+ years; keep an emergency fund separate.",
    ]

    fire = fire_number(cf["annual_expense"])
    ytf = None
    if surplus > 0 and fire["fire_number"] > 0:
        ytf = years_to_target(fire["fire_number"], 0, surplus + target_invest)

    return {
        "currency": currency,
        "cashflow": cf,
        "active_subscription_burn": active_burn,
        "inactive_subscription_monthly": inactive_monthly,
        "recommended_monthly_investment": target_invest,
        "fire": fire,
        "years_to_financial_independence": ytf,
        "tips": tips,
        "principles": principles,
        "disclaimer": "Educational only — not licensed financial advice. "
                      "Assumes an 8%/yr long-run return, which is not guaranteed.",
    }
