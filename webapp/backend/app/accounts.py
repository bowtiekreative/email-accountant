"""Webapp wrapper around the shared accounts config (repo-root accounts.py).

Lets the Accounts screen list/add/update/remove Gmail and IMAP accounts. The
underlying file (~/.email-accountant/accounts.json) is the single source of
truth the scanners read.
"""

import sys
from pathlib import Path
from typing import Any, Optional

# The shared config lives at the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import accounts as _accounts  # noqa: E402


def list_accounts() -> list[dict[str, Any]]:
    return _accounts.public_view()


def add_account(label: str, email: str, provider: str = "gmail",
                password: Optional[str] = None, password_env: Optional[str] = None,
                imap_host: Optional[str] = None,
                imap_port: Optional[int] = None) -> dict[str, Any]:
    _accounts.add_account(
        label=label, email=email, provider=provider, password=password,
        password_env=password_env, imap_host=imap_host, imap_port=imap_port,
    )
    return {"label": label, "added": True}


def update_account(label: str, **fields) -> dict[str, Any]:
    _accounts.update_account(label, **fields)
    return {"label": label, "updated": True}


def delete_account(label: str) -> dict[str, Any]:
    _accounts.delete_account(label)
    return {"label": label, "deleted": True}
