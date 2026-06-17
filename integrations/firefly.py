"""Firefly III connector — personal spending & income.

Firefly models double-entry transactions: a "withdrawal" moves money out of an
asset account (an expense), a "deposit" moves money in (income).
"""

from typing import Any

from . import config
from ._http import request
from .normalize import NormalizedTxn


def _headers(cfg) -> dict:
    return {
        "Authorization": f"Bearer {cfg.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def available() -> bool:
    cfg = config.firefly()
    return cfg.enabled and bool(cfg.token)


def create_transaction(txn: NormalizedTxn) -> dict[str, Any]:
    cfg = config.firefly()
    if not available():
        return {"skipped": "firefly disabled or no token"}

    asset = cfg.extra["asset_account"]
    if txn.direction == "income":
        ff_type = "deposit"
        source_name = txn.merchant            # money comes from the payer
        destination_name = asset
    else:
        ff_type = "withdrawal"
        source_name = asset                   # money leaves your asset account
        destination_name = txn.merchant       # to the merchant (expense account)

    split = {
        "type": ff_type,
        "date": txn.date,
        "amount": f"{txn.amount:.2f}",
        "description": (txn.description or txn.merchant)[:255],
        "currency_code": txn.currency,
        "source_name": source_name,
        "destination_name": destination_name,
        "category_name": txn.category or "Uncategorized",
        "tags": [t for t in ["email-accountant", txn.domain, txn.account_label] if t],
        "notes": f"source_id={txn.source_id}",
    }
    payload = {"error_if_duplicate_hash": True, "transactions": [split]}

    try:
        result = request(
            "POST", f"{cfg.base_url}/api/v1/transactions",
            headers=_headers(cfg), json=payload,
        )
    except Exception as exc:  # noqa: BLE001 - surface duplicates as a skip
        if "Duplicate" in str(exc) or "duplicate" in str(exc):
            return {"skipped": "duplicate in firefly"}
        raise
    tx_id = None
    try:
        tx_id = result["data"]["id"]
    except (KeyError, TypeError):
        pass
    return {"created": True, "firefly_id": tx_id, "type": ff_type}
