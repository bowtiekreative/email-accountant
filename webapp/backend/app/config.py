"""Configuration for the Email Accountant webapp backend.

Everything is driven by environment variables so the same service works
local-only (SQLite, the default) or pointed at a hosted Supabase/Postgres.
"""

import os
from pathlib import Path

# Where the year-partitioned SQLite ledgers live. Matches db/database.py.
DB_DIR = os.environ.get(
    "EMAIL_ACCOUNTANT_DB_DIR",
    str(Path.home() / ".email-accountant" / "data"),
)

# Earliest tax year the app supports. Every year from here to the current year
# is always selectable in the UI, even before it has data.
START_YEAR = int(os.environ.get("EMAIL_ACCOUNTANT_START_YEAR", "2006"))

REPO_ROOT = Path(__file__).resolve().parents[3]

# "Scan recent" — fast incremental scan (last few days).
SCAN_COMMAND = os.environ.get(
    "EMAIL_ACCOUNTANT_SCAN_CMD",
    f"python {REPO_ROOT / 'scan_daily.py'}",
)

# "Full history" — backfills every email back to inception (2006-onward).
FULL_SCAN_COMMAND = os.environ.get(
    "EMAIL_ACCOUNTANT_FULL_SCAN_CMD",
    f"python {REPO_ROOT / 'scan_full_archive_fast.py'}",
)

# CORS origin for the Next.js dev server.
FRONTEND_ORIGIN = os.environ.get(
    "EMAIL_ACCOUNTANT_FRONTEND_ORIGIN", "http://localhost:3000"
)
