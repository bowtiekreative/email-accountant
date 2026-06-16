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

# Command run when the "Scan now" button is pressed. Defaults to the repo's
# daily incremental scanner. Override to point at any scan script you prefer.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCAN_COMMAND = os.environ.get(
    "EMAIL_ACCOUNTANT_SCAN_CMD",
    f"python {REPO_ROOT / 'scan_daily.py'}",
)

# CORS origin for the Next.js dev server.
FRONTEND_ORIGIN = os.environ.get(
    "EMAIL_ACCOUNTANT_FRONTEND_ORIGIN", "http://localhost:3000"
)
