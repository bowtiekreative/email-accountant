"""Ask AI — a spending assistant powered by Claude.

Builds a compact, factual snapshot of the user's finances from the ledger and
asks Claude to answer questions about it. Configure with:

  ANTHROPIC_API_KEY        required to enable Ask AI
  LEDGER_ASSISTANT_MODEL   optional, defaults to claude-sonnet-4-6
"""

import os
from datetime import datetime
from typing import Any

from . import ledger

DEFAULT_MODEL = os.environ.get("LEDGER_ASSISTANT_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = (
    "You are Ledger, a calm, plain-spoken financial assistant inside an app that "
    "reads a person's email receipts and sorts their expenses. Bow Tie Kreative makes Ledger.\n\n"
    "Voice: warm, encouraging, never hypey or jargon-y — like a competent friend. "
    "Use sentence case. Keep answers short and scannable, one idea per sentence, with "
    "generous breathing room. Prefer concrete numbers from the data you're given.\n\n"
    "Only answer from the spending snapshot provided. If something isn't in the data, say so "
    "kindly and suggest scanning the inbox or adding the detail. You can talk about budgets, "
    "categories, vendors, what looks tax-deductible, and quick monthly summaries. "
    "You are not a licensed financial, tax, or investment advisor — add a one-line, friendly "
    "reminder of that only when giving tax or investment guidance."
)


def assistant_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _money(n: float, currency: str) -> str:
    sym = {"USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£"}.get(currency, "")
    return f"{sym}{n:,.2f}"


def build_context(currency: str = "USD") -> str:
    """A short text snapshot of the current year's finances for the model."""
    year = datetime.now().year
    try:
        ov: dict[str, Any] = ledger.overview(year=year, currency=currency)
    except Exception:
        return "No spending data is available yet."

    totals = (ov.get("totals_by_currency") or {}).get(currency, {})
    lines: list[str] = [f"Spending snapshot for {year} ({currency}):"]
    if totals:
        lines.append(
            f"- Income: {_money(totals.get('income', 0), currency)}; "
            f"Expenses: {_money(totals.get('expense', 0), currency)}; "
            f"Net: {_money(totals.get('net', 0), currency)}; "
            f"Transactions: {totals.get('transaction_count', 0)}; "
            f"Deductible: {_money(totals.get('deductible', 0), currency)}"
        )
    if ov.get("needs_review"):
        lines.append(f"- {ov['needs_review']} transactions still need review.")

    cats = (ov.get("by_category") or [])[:8]
    if cats:
        lines.append("- Top categories: " + ", ".join(
            f"{c['name']} {_money(c['total'], currency)} ({c['count']})" for c in cats
        ))
    merch = (ov.get("by_merchant") or [])[:8]
    if merch:
        lines.append("- Top vendors: " + ", ".join(
            f"{m['name']} {_money(m['total'], currency)}" for m in merch
        ))
    trend = ov.get("monthly_trend") or []
    if trend:
        lines.append("- Monthly expense trend: " + ", ".join(
            f"{t['month']}={_money(t.get('expense', 0), currency)}" for t in trend[-6:]
        ))
    return "\n".join(lines)


def chat(messages: list[dict[str, str]], currency: str = "USD") -> dict[str, Any]:
    """Answer a conversation. `messages` is [{role: user|assistant, content}]."""
    if not assistant_enabled():
        raise RuntimeError(
            "Ask AI isn't configured. Add an ANTHROPIC_API_KEY to the backend environment."
        )
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY
    context = build_context(currency)

    convo = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if not convo:
        convo = [{"role": "user", "content": "Give me a quick summary of my spending."}]

    resp = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1024,
        system=f"{SYSTEM_PROMPT}\n\n---\n{context}",
        messages=convo,
    )
    reply = "".join(block.text for block in resp.content if block.type == "text")
    return {"reply": reply.strip(), "model": DEFAULT_MODEL}
