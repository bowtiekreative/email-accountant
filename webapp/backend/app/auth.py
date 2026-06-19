"""Authentication: a single admin login, hashed password, signed session tokens.

- Passwords are stored as PBKDF2-HMAC-SHA256 (200k iterations) with a random
  per-user salt — never in plaintext.
- Sessions are HMAC-signed tokens (payload.signature) with an expiry.
- Credentials live in $EMAIL_ACCOUNTANT_HOME/auth.json (chmod 600), seeded once
  from ADMIN_USERNAME / ADMIN_PASSWORD env vars.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(
    os.environ.get("EMAIL_ACCOUNTANT_HOME", str(Path.home() / ".email-accountant"))
)
AUTH_FILE = CONFIG_DIR / "auth.json"
ITERATIONS = 200_000
TOKEN_TTL = 7 * 24 * 3600  # 7 days


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hash(password: str, salt: bytes) -> str:
    return _b64(hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS))


def _load() -> dict:
    try:
        return json.loads(AUTH_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(AUTH_FILE, 0o600)
    except OSError:
        pass


def ensure_admin() -> dict:
    """Seed the admin user + signing secret on first run."""
    data = _load()
    changed = False
    if "secret" not in data:
        data["secret"] = secrets.token_hex(32)
        changed = True
    if not data.get("users"):
        user = os.environ.get("ADMIN_USERNAME", "admin")
        pw = os.environ.get("ADMIN_PASSWORD", "admin")
        salt = secrets.token_bytes(16)
        data["users"] = {user: {"salt": salt.hex(), "hash": _hash(pw, salt)}}
        changed = True
    if changed:
        _save(data)
    return data


def verify(username: str, password: str) -> bool:
    data = ensure_admin()
    u = data["users"].get(username)
    if not u:
        return False
    candidate = _hash(password, bytes.fromhex(u["salt"]))
    return hmac.compare_digest(candidate, u["hash"])


def make_token(username: str) -> str:
    data = ensure_admin()
    payload = _b64(json.dumps({"u": username, "exp": int(time.time()) + TOKEN_TTL}).encode())
    sig = _b64(hmac.new(data["secret"].encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    data = ensure_admin()
    payload, _, sig = token.partition(".")
    expected = _b64(hmac.new(data["secret"].encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        obj = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if obj.get("exp", 0) < time.time():
        return None
    if obj.get("u") not in data.get("users", {}):
        return None
    return obj["u"]


def change_password(username: str, old_password: str, new_password: str) -> bool:
    if not verify(username, old_password):
        return False
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters")
    data = ensure_admin()
    salt = secrets.token_bytes(16)
    data["users"][username] = {"salt": salt.hex(), "hash": _hash(new_password, salt)}
    _save(data)
    return True
