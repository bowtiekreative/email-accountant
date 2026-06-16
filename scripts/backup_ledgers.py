#!/usr/bin/env python3
"""Back up every SQLite ledger to a timestamped folder.

Usage:
    python scripts/backup_ledgers.py [destination_dir]

Defaults: copies ~/.email-accountant/data/*.db into
~/.email-accountant/backups/<UTC timestamp>/. Set EMAIL_ACCOUNTANT_DB_DIR to
change the source. Safe to run from cron.
"""
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path(
    os.environ.get(
        "EMAIL_ACCOUNTANT_DB_DIR", str(Path.home() / ".email-accountant" / "data")
    )
)


def backup(dest_root: Path | None = None) -> Path:
    dest_root = dest_root or (Path.home() / ".email-accountant" / "backups")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_root / stamp
    dest.mkdir(parents=True, exist_ok=True)

    db_files = sorted(DB_DIR.glob("*.db"))
    for f in db_files:
        # Use SQLite's backup API for a consistent copy even if the DB is open.
        import sqlite3

        src = sqlite3.connect(str(f))
        dst = sqlite3.connect(str(dest / f.name))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    return dest


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    out = backup(target)
    count = len(list(out.glob("*.db")))
    print(f"✅ Backed up {count} ledger file(s) to {out}")
