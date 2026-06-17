"""Routes a normalized transaction into the stack and records it in Strapi.

Flow per transaction:
  1. Skip if Strapi already has it (dedup by source_id) unless force=True.
  2. Upload any attachments to Paperless (OCR + archive).
  3. Route the financial entry: business -> Akaunting, personal -> Firefly
     (overridable via Strapi routing-rules or env).
  4. Upsert the unified record + cross-references into Strapi and log the sync.
"""

from datetime import datetime, timezone
from typing import Any

from . import akaunting, config, firefly, paperless, strapi
from .normalize import NormalizedTxn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_transaction(txn: NormalizedTxn, force: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"source_id": txn.source_id, "actions": {}}

    # 1. Dedup via Strapi.
    if not force and strapi.available():
        if strapi.find_transaction(txn.source_id):
            result["status"] = "skipped (already synced)"
            return result

    # 2. Attachments -> Paperless.
    doc_results = []
    if txn.attachments and paperless.available():
        for att in txn.attachments:
            doc_results.append(paperless.upload_document(
                att.path, title=f"{txn.merchant} {txn.date}", created=txn.date,
            ))
    result["actions"]["paperless"] = doc_results

    # 3. Route the financial entry.
    routes = config.routing()
    routes.update(strapi.routing_overrides())
    target = routes.get(txn.domain, routes.get("unknown", "firefly"))

    if target == "akaunting":
        fin = akaunting.create_transaction(txn)
    else:
        fin = firefly.create_transaction(txn)
    result["actions"][target] = fin
    result["routed_to"] = target

    # 4. Unified record + sync log in Strapi.
    record = {
        "source_id": txn.source_id,
        "date": txn.date,
        "amount": txn.amount,
        "currency": txn.currency,
        "direction": txn.direction,
        "domain": txn.domain,
        "merchant": txn.merchant,
        "category": txn.category,
        "account_label": txn.account_label,
        "routed_to": target,
        "akaunting_id": fin.get("akaunting_id"),
        "firefly_id": fin.get("firefly_id"),
        "paperless_tasks": [d.get("task_id") for d in doc_results if d.get("task_id")],
        "synced_at": _now(),
    }
    result["actions"]["strapi"] = strapi.upsert_transaction(record)
    strapi.log_sync({
        "source_id": txn.source_id, "routed_to": target,
        "status": "ok", "synced_at": _now(),
    })
    result["status"] = "synced"
    return result


def route_many(txns: list[NormalizedTxn], force: bool = False) -> dict[str, Any]:
    summary = {"total": len(txns), "synced": 0, "skipped": 0, "errors": 0, "results": []}
    for txn in txns:
        try:
            r = route_transaction(txn, force=force)
            summary["results"].append(r)
            if r.get("status", "").startswith("skipped"):
                summary["skipped"] += 1
            else:
                summary["synced"] += 1
        except Exception as exc:  # noqa: BLE001 - keep going, record the failure
            summary["errors"] += 1
            summary["results"].append({"source_id": txn.source_id, "error": str(exc)})
    return summary
