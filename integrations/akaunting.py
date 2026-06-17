"""Akaunting connector — business income, expenses, bills, and clients/vendors.

Akaunting's REST API is scoped to a company (``company_id``) and authenticates
with HTTP basic auth (user email + password) or a bearer token. Transactions
require a category and a bank account; we resolve/create the category and the
contact (customer for income, vendor for expense) by name.
"""

import os
from typing import Any, Optional

from . import config
from ._http import request


def _auth_and_headers(cfg):
    headers = {"Accept": "application/json", "X-Company": str(cfg.extra["company_id"])}
    auth = None
    if cfg.token:
        headers["Authorization"] = f"Bearer {cfg.token}"
    elif cfg.extra.get("email") and cfg.extra.get("password"):
        auth = (cfg.extra["email"], cfg.extra["password"])
    return headers, auth


def available() -> bool:
    cfg = config.akaunting()
    return cfg.enabled and (bool(cfg.token) or bool(cfg.extra.get("email")))


def _params(cfg, **extra):
    p = {"company_id": cfg.extra["company_id"], "limit": 100}
    p.update(extra)
    return p


def ensure_category(name: str, cat_type: str) -> Optional[int]:
    """Find or create an income/expense category by name; return its id."""
    cfg = config.akaunting()
    headers, auth = _auth_and_headers(cfg)
    name = name or ("Income" if cat_type == "income" else "Other")
    found = request("GET", f"{cfg.base_url}/api/categories",
                    headers=headers, auth=auth, params=_params(cfg, search=name))
    for item in (found.get("data") or []):
        if item.get("name", "").lower() == name.lower() and item.get("type") == cat_type:
            return item["id"]
    created = request("POST", f"{cfg.base_url}/api/categories",
                      headers=headers, auth=auth, params=_params(cfg),
                      json={"name": name, "type": cat_type, "color": "#6da252",
                            "enabled": 1, "company_id": cfg.extra["company_id"]})
    return (created.get("data") or {}).get("id")


def ensure_contact(name: str, contact_type: str) -> Optional[int]:
    """Find or create a customer/vendor by name; return its id."""
    cfg = config.akaunting()
    headers, auth = _auth_and_headers(cfg)
    if not name:
        return None
    found = request("GET", f"{cfg.base_url}/api/contacts",
                    headers=headers, auth=auth, params=_params(cfg, search=name))
    for item in (found.get("data") or []):
        if item.get("name", "").lower() == name.lower():
            return item["id"]
    created = request("POST", f"{cfg.base_url}/api/contacts",
                      headers=headers, auth=auth, params=_params(cfg),
                      json={"name": name, "type": contact_type, "enabled": 1,
                            "currency_code": "USD", "company_id": cfg.extra["company_id"]})
    return (created.get("data") or {}).get("id")


def create_transaction(txn) -> dict[str, Any]:
    """Create an Akaunting income/expense transaction from a NormalizedTxn."""
    cfg = config.akaunting()
    if not available():
        return {"skipped": "akaunting disabled or no credentials"}

    headers, auth = _auth_and_headers(cfg)
    ak_type = "income" if txn.direction == "income" else "expense"
    category_id = ensure_category(txn.tax_category or txn.category or "", ak_type)
    contact_id = ensure_contact(txn.merchant, "customer" if ak_type == "income" else "vendor")

    payload = {
        "company_id": cfg.extra["company_id"],
        "type": ak_type,
        "account_id": int(cfg.extra["bank_account_id"]),
        "paid_at": f"{txn.date} 00:00:00",
        "amount": round(txn.amount, 2),
        "currency_code": txn.currency,
        "currency_rate": 1,
        "category_id": category_id,
        "contact_id": contact_id,
        "payment_method": os.environ.get("AKAUNTING_PAYMENT_METHOD", "offline-payments.cash.1"),
        "description": (txn.description or txn.merchant)[:500],
        "reference": txn.source_id,
    }
    result = request("POST", f"{cfg.base_url}/api/transactions",
                     headers=headers, auth=auth, params=_params(cfg), json=payload)
    return {"created": True, "akaunting_id": (result.get("data") or {}).get("id"),
            "type": ak_type}
