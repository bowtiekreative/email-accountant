"""Strapi connector — the orchestration layer.

Strapi holds a unified index of every transaction (with cross-references to the
Paperless document, and the Akaunting/Firefly entry it was routed to), a sync
log, and optional routing-rule overrides. This is the single place to query
"what happened to this receipt across all the tools".
"""

from typing import Any, Optional

from . import config
from ._http import request


def _headers(cfg) -> dict:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if cfg.token:
        h["Authorization"] = f"Bearer {cfg.token}"
    return h


def available() -> bool:
    cfg = config.strapi()
    return cfg.enabled and bool(cfg.token)


def find_transaction(source_id: str) -> Optional[dict[str, Any]]:
    cfg = config.strapi()
    if not available():
        return None
    res = request(
        "GET", f"{cfg.base_url}/api/transactions",
        headers=_headers(cfg),
        params={"filters[source_id][$eq]": source_id, "pagination[pageSize]": 1},
    )
    data = res.get("data") or []
    return data[0] if data else None


def upsert_transaction(record: dict[str, Any]) -> dict[str, Any]:
    """Create or update the unified transaction record keyed by source_id."""
    cfg = config.strapi()
    if not available():
        return {"skipped": "strapi disabled or no token"}

    existing = find_transaction(record["source_id"])
    if existing:
        eid = existing.get("documentId") or existing.get("id")
        res = request("PUT", f"{cfg.base_url}/api/transactions/{eid}",
                      headers=_headers(cfg), json={"data": record})
        return {"updated": True, "id": eid, "data": res.get("data")}
    res = request("POST", f"{cfg.base_url}/api/transactions",
                  headers=_headers(cfg), json={"data": record})
    data = res.get("data") or {}
    return {"created": True, "id": data.get("documentId") or data.get("id"), "data": data}


def log_sync(entry: dict[str, Any]) -> dict[str, Any]:
    cfg = config.strapi()
    if not available():
        return {"skipped": "strapi disabled or no token"}
    res = request("POST", f"{cfg.base_url}/api/sync-logs",
                  headers=_headers(cfg), json={"data": entry})
    return {"logged": True, "data": res.get("data")}


def routing_overrides() -> dict[str, str]:
    """Optional per-domain routing overrides configured in Strapi."""
    cfg = config.strapi()
    if not available():
        return {}
    try:
        res = request("GET", f"{cfg.base_url}/api/routing-rules",
                      headers=_headers(cfg), params={"pagination[pageSize]": 100})
    except Exception:
        return {}
    overrides = {}
    for item in (res.get("data") or []):
        attrs = item.get("attributes", item)
        if attrs.get("domain") and attrs.get("target"):
            overrides[attrs["domain"]] = attrs["target"]
    return overrides
