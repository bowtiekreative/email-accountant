#!/usr/bin/env python3
"""Bridge: push transactions from the email-accountant ledger into the stack
(Paperless / Akaunting / Firefly, orchestrated by Strapi).

Usage:
    python sync_to_stack.py [--year YEAR] [--limit N] [--force] [--dry-run]

The email scanner stays the ingestion engine; this routes its output into the
self-hosted tools. Dedup is handled by Strapi (by source_id), so re-running is
safe. Configure services via .env.stack (see .env.stack.example).
"""

import argparse
import glob
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from integrations import orchestrator  # noqa: E402
from integrations.normalize import from_ledger_row  # noqa: E402

DB_DIR = os.environ.get(
    "EMAIL_ACCOUNTANT_DB_DIR", str(Path.home() / ".email-accountant" / "data")
)


def _account_map(conn) -> dict:
    has = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='email_accounts'"
    ).fetchone()
    if not has:
        return {}
    return {r["id"]: r["label"] for r in conn.execute("SELECT id, label FROM email_accounts")}


def read_ledger(year=None, limit=100000) -> list:
    rows = []
    for path in sorted(glob.glob(os.path.join(DB_DIR, "email_accountant*.db"))):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            has = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone()
            if not has:
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            amap = _account_map(conn)
            q = "SELECT * FROM transactions"
            params = []
            if year:
                q += " WHERE substr(email_date,1,4) = ?"
                params.append(str(year))
            for r in conn.execute(q, params):
                d = dict(r)
                d["account"] = amap.get(d.get("account_id"))
                rows.append(from_ledger_row(d, db_stem=stem))
        finally:
            conn.close()
    # Dedup identical source ids that appear in both the main + year db.
    seen, unique = set(), []
    for t in rows:
        if t.source_id in seen:
            continue
        seen.add(t.source_id)
        unique.append(t)
    return unique[:limit]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int)
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--force", action="store_true", help="re-sync even if already in Strapi")
    ap.add_argument("--dry-run", action="store_true", help="list what would sync, don't send")
    args = ap.parse_args()

    txns = read_ledger(year=args.year, limit=args.limit)
    print(f"📒 {len(txns)} ledger transaction(s) to route"
          + (f" (year {args.year})" if args.year else ""))

    if args.dry_run:
        for t in txns[:25]:
            print(f"  {t.date}  {t.domain:8} {t.direction:7} {t.currency} "
                  f"{t.amount:>9.2f}  {t.merchant[:30]}  [{len(t.attachments)} doc]")
        if len(txns) > 25:
            print(f"  … and {len(txns) - 25} more")
        return

    summary = orchestrator.route_many(txns, force=args.force)
    print(f"✅ synced={summary['synced']} skipped={summary['skipped']} "
          f"errors={summary['errors']}")
    for r in summary["results"]:
        if r.get("error"):
            print(f"  ❌ {r['source_id']}: {r['error']}")


if __name__ == "__main__":
    main()
