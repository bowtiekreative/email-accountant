"""A provider-neutral transaction model that the connectors consume.

The email pipeline (db/transactions) and any other source map onto this shape,
so routing logic doesn't depend on any one tool's schema.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Attachment:
    path: str
    filename: str
    mime_type: Optional[str] = None


@dataclass
class NormalizedTxn:
    # Stable identity for dedup across re-syncs.
    source_id: str                      # e.g. "ledger:email_accountant_2025:42"
    date: str                           # YYYY-MM-DD
    amount: float                       # always positive
    currency: str                       # USD / CAD
    direction: str                      # "income" | "expense" | "transfer"
    domain: str                         # "business" | "personal" | "unknown"
    merchant: str
    description: str = ""
    category: Optional[str] = None
    tax_category: Optional[str] = None
    is_deductible: bool = False
    account_label: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def from_ledger_row(row: dict[str, Any], db_stem: str = "ledger") -> NormalizedTxn:
    """Build a NormalizedTxn from an email-accountant transactions row."""
    rid = row.get("id")
    date = (row.get("transaction_date") or (row.get("email_date") or "")[:10] or "")[:10]
    amount = abs(float(row.get("amount") or 0))
    direction = row.get("transaction_type") or "expense"

    attachments = []
    ap = row.get("attachment_path")
    if ap:
        import os
        attachments.append(Attachment(path=ap, filename=os.path.basename(ap)))

    return NormalizedTxn(
        source_id=f"ledger:{db_stem}:{rid}",
        date=date,
        amount=amount,
        currency=(row.get("currency") or "USD").upper(),
        direction=direction,
        domain=row.get("domain") or "unknown",
        merchant=row.get("merchant_name") or "Unknown",
        description=row.get("email_subject") or row.get("description") or "",
        category=row.get("category"),
        tax_category=row.get("tax_category"),
        is_deductible=bool(row.get("is_deductible")),
        account_label=row.get("account"),
        attachments=attachments,
        meta={
            "email_id": row.get("email_id"),
            "classification_method": row.get("classification_method"),
            "classification_confidence": row.get("classification_confidence"),
        },
    )
