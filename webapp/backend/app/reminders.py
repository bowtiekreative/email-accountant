"""Reminders engine: budget overruns, upcoming subscription renewals, review
backlog, and tax deadlines. Can preview in the UI or email a digest (cron)."""

import os
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Any, Optional

from . import ledger, planning

_FREQ_DAYS = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}


def _current_month_spend(currency: str) -> dict[str, float]:
    month = datetime.now().strftime("%Y-%m")
    out: dict[str, float] = defaultdict(float)
    for t in ledger.list_transactions(currency=currency, limit=1_000_000):
        if t.get("transaction_type") == "expense" and (t.get("email_date") or "").startswith(month):
            out[t.get("category") or "Uncategorized"] += t.get("amount") or 0
    return out


def build_reminders(currency: Optional[str] = None) -> list[dict[str, Any]]:
    """Build the list of actionable reminders (newest/most-severe first)."""
    reminders: list[dict[str, Any]] = []
    currencies = [currency] if currency else ledger.available_currencies()
    now = datetime.now()

    for cur in currencies:
        # 1. Budget overruns this month.
        budgets = {b["category"]: b for b in planning.list_budgets() if b.get("currency") == cur}
        spend = _current_month_spend(cur)
        for cat, b in budgets.items():
            spent = spend.get(cat, 0.0)
            limit = b["monthly_limit"]
            if limit and spent > limit:
                reminders.append({
                    "type": "budget_overrun",
                    "severity": "high",
                    "currency": cur,
                    "message": f"Over budget on {cat}: {spent:.0f} / {limit:.0f} {cur} this month.",
                })
            elif limit and spent >= limit * 0.8:
                reminders.append({
                    "type": "budget_warning",
                    "severity": "medium",
                    "currency": cur,
                    "message": f"Near budget on {cat}: {spent:.0f} / {limit:.0f} {cur} this month.",
                })

        # 2. Upcoming subscription renewals (within 7 days).
        for s in planning.subscriptions(currency=cur)["subscriptions"]:
            if not s["active"]:
                continue
            try:
                last = datetime.fromisoformat(s["last_charge"])
            except ValueError:
                continue
            nxt = last + timedelta(days=_FREQ_DAYS.get(s["frequency"], 30))
            days = (nxt - now).days
            if 0 <= days <= 7:
                reminders.append({
                    "type": "subscription_renewal",
                    "severity": "medium",
                    "currency": cur,
                    "message": (
                        f"{s['merchant']} ({s['frequency']}) renews ~{nxt.date().isoformat()} "
                        f"for {s['typical_amount']:.2f} {cur}."
                    ),
                })

    # 3. Review backlog (currency-agnostic).
    pending = len(ledger.list_transactions(needs_review=True, limit=1_000_000))
    if pending:
        reminders.append({
            "type": "review_backlog",
            "severity": "low",
            "currency": None,
            "message": f"{pending} transaction(s) need review.",
        })

    # 4. Tax deadline (CRA personal filing: Apr 30).
    deadline = datetime(now.year, 4, 30)
    if now <= deadline:
        days = (deadline - now).days
        if days <= 60:
            reminders.append({
                "type": "tax_deadline",
                "severity": "high" if days <= 21 else "medium",
                "currency": None,
                "message": f"CRA filing deadline (Apr 30) is in {days} days — review your T2125.",
            })

    order = {"high": 0, "medium": 1, "low": 2}
    reminders.sort(key=lambda r: order.get(r["severity"], 3))
    return reminders


def _smtp_settings() -> Optional[dict]:
    """Pull SMTP settings from env, falling back to Gmail app-password setup."""
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER")
    pwd = os.environ.get("SMTP_PASS") or os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("REMINDER_TO") or user
    if not (user and pwd and to):
        return None
    if not host:
        host = "smtp.gmail.com"
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "pwd": pwd,
        "from": os.environ.get("REMINDER_FROM", user),
        "to": to,
    }


def send_reminders(currency: Optional[str] = None) -> dict[str, Any]:
    """Email the reminder digest. Returns status; no-op if nothing to send."""
    reminders = build_reminders(currency)
    if not reminders:
        return {"sent": False, "reason": "no reminders", "count": 0}

    cfg = _smtp_settings()
    if not cfg:
        return {
            "sent": False,
            "reason": "SMTP not configured (set SMTP_* or GMAIL_USER/GMAIL_APP_PASSWORD + REMINDER_TO)",
            "count": len(reminders),
            "reminders": reminders,
        }

    lines = ["Your Email Accountant reminders:", ""]
    for r in reminders:
        lines.append(f"• [{r['severity'].upper()}] {r['message']}")
    body = "\n".join(lines)

    msg = MIMEText(body)
    msg["Subject"] = f"📬 Email Accountant — {len(reminders)} reminder(s)"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]

    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["pwd"])
        server.sendmail(cfg["from"], [cfg["to"]], msg.as_string())

    return {"sent": True, "count": len(reminders), "to": cfg["to"]}
