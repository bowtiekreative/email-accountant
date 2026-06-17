"""Single source of truth for the email accounts to scan.

Accounts live in ~/.email-accountant/accounts.json (outside the repo, so
credentials are never committed). Both scanners and the webapp read/write this
file, so you configure accounts in one place — Gmail or any IMAP provider.

Account shape:
    {
        "label": "personal",
        "email": "you@example.com",
        "provider": "gmail",          # gmail | imap
        "imap_host": "imap.gmail.com",  # auto-filled for gmail
        "imap_port": 993,
        "password_env": "GMAIL_PRIMARY_PASSWORD",  # read password from this env var
        "password": null,             # ...or store it inline (local secret)
        "active": true
    }
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path(
    os.environ.get("EMAIL_ACCOUNTANT_HOME", str(Path.home() / ".email-accountant"))
)
ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"

# Common IMAP hosts so users only pick a provider, not a server.
PROVIDER_HOSTS = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "office365": ("outlook.office365.com", 993),
    "yahoo": ("imap.mail.yahoo.com", 993),
    "icloud": ("imap.mail.me.com", 993),
}

# Seeded into accounts.json the first time, so existing setups keep working.
DEFAULT_ACCOUNTS = [
    ("personal", "ryan@bowtiekreative.com", "GMAIL_PRIMARY_PASSWORD"),
    ("theapprentice4", "theapprentice4@gmail.com", "GMAIL_APPRENTICE_PASSWORD"),
    ("digitalstemcell", "digitalstemcell@gmail.com", "GMAIL_DIGITALSTEMCELL_PASSWORD"),
    ("bowtiekreative", "bowtiekreative@gmail.com", "GMAIL_BOWTIEKREATIVE_PASSWORD"),
    ("k6rb1n", "k6rb1n@gmail.com", "GMAIL_K6RB1N_PASSWORD"),
    ("bnelsonblog1", "bnelsonblog1@gmail.com", "GMAIL_BNELSONBLOG1_PASSWORD"),
    ("hustlezonetv", "hustlezonetv@gmail.com", "GMAIL_HUSTLEZONETV_PASSWORD"),
]


def _normalize(acct: dict[str, Any]) -> dict[str, Any]:
    """Fill in defaults (provider host/port, active flag)."""
    provider = (acct.get("provider") or "gmail").lower()
    host, port = PROVIDER_HOSTS.get(provider, (acct.get("imap_host"), 993))
    acct.setdefault("provider", provider)
    acct["imap_host"] = acct.get("imap_host") or host
    acct["imap_port"] = int(acct.get("imap_port") or port or 993)
    acct.setdefault("active", True)
    acct.setdefault("password_env", None)
    acct.setdefault("password", None)
    return acct


def _seed_default() -> dict[str, Any]:
    data = {
        "accounts": [
            _normalize({
                "label": label, "email": email, "provider": "gmail",
                "password_env": env, "active": True,
            })
            for label, email, env in DEFAULT_ACCOUNTS
        ]
    }
    save(data)
    return data


def load() -> dict[str, Any]:
    """Load the accounts config, seeding defaults on first run."""
    if not ACCOUNTS_FILE.exists():
        return _seed_default()
    try:
        with open(ACCOUNTS_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"accounts": []}
    data["accounts"] = [_normalize(a) for a in data.get("accounts", [])]
    return data


def save(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    # Credentials live here — keep the file private.
    try:
        os.chmod(ACCOUNTS_FILE, 0o600)
    except OSError:
        pass


def resolve_password(acct: dict[str, Any]) -> Optional[str]:
    """Inline password wins; otherwise read from the named env var."""
    if acct.get("password"):
        return acct["password"]
    env = acct.get("password_env")
    if env:
        return os.environ.get(env)
    return None


def get_accounts(active_only: bool = True) -> list[dict[str, Any]]:
    """Accounts with their resolved password, ready for the scanners."""
    out = []
    for a in load().get("accounts", []):
        if active_only and not a.get("active", True):
            continue
        acct = dict(a)
        acct["password"] = resolve_password(a)
        out.append(acct)
    return out


# ---------------------------------------------------------------------------
# Mutations (used by the webapp Accounts screen)
# ---------------------------------------------------------------------------

def add_account(label: str, email: str, provider: str = "gmail",
                password: Optional[str] = None, password_env: Optional[str] = None,
                imap_host: Optional[str] = None, imap_port: Optional[int] = None) -> dict:
    data = load()
    if any(a["label"] == label for a in data["accounts"]):
        raise ValueError(f"Account '{label}' already exists")
    acct = _normalize({
        "label": label, "email": email, "provider": provider,
        "password": password, "password_env": password_env,
        "imap_host": imap_host, "imap_port": imap_port, "active": True,
    })
    data["accounts"].append(acct)
    save(data)
    return acct


def update_account(label: str, **fields) -> dict:
    data = load()
    for a in data["accounts"]:
        if a["label"] == label:
            for k, v in fields.items():
                if v is not None:
                    a[k] = v
            _normalize(a)
            save(data)
            return a
    raise ValueError(f"Account '{label}' not found")


def delete_account(label: str) -> None:
    data = load()
    data["accounts"] = [a for a in data["accounts"] if a["label"] != label]
    save(data)


def public_view() -> list[dict[str, Any]]:
    """Account list for the UI — never exposes stored passwords."""
    out = []
    for a in load().get("accounts", []):
        out.append({
            "label": a["label"],
            "email": a["email"],
            "provider": a.get("provider", "gmail"),
            "imap_host": a.get("imap_host"),
            "imap_port": a.get("imap_port"),
            "active": a.get("active", True),
            "has_password": bool(resolve_password(a)),
            "password_source": "inline" if a.get("password") else (
                a.get("password_env") if a.get("password_env") else None
            ),
        })
    return out
