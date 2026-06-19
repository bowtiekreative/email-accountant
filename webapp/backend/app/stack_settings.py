"""Read/write the stack connection config from the dashboard, and test each
service. Persists to the same file the connectors read
(``$EMAIL_ACCOUNTANT_HOME/stack_config.json``)."""

import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The stack connectors are optional; never let a packaging gap crash the API.
try:
    from integrations import config as stack_config  # noqa: E402
except Exception:  # pragma: no cover
    stack_config = None

CONFIG_DIR = Path(
    os.environ.get("EMAIL_ACCOUNTANT_HOME", str(Path.home() / ".email-accountant"))
)
CONFIG_FILE = CONFIG_DIR / "stack_config.json"

SERVICES = ("paperless", "akaunting", "firefly", "strapi")
# Which fields each service exposes in the UI (besides url/token/enabled).
EXTRA_FIELDS = {
    "akaunting": ["email", "company_id", "account_id"],
    "firefly": ["asset_account"],
}
SECRET_FIELDS = {"token", "password"}


def _load() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def public_view() -> dict[str, Any]:
    """Config for the UI — secrets shown only as has_<field> booleans."""
    data = _load()
    out: dict[str, Any] = {}
    for svc in SERVICES:
        cfg = data.get(svc, {})
        view = {
            "url": cfg.get("url", ""),
            "enabled": cfg.get("enabled", True),
            "has_token": bool(cfg.get("token")),
        }
        for f in EXTRA_FIELDS.get(svc, []):
            view[f] = cfg.get(f, "")
        if svc == "akaunting":
            view["has_password"] = bool(cfg.get("password"))
        out[svc] = view
    out["routing"] = data.get("routing", {})
    return out


def update(svc: str, fields: dict[str, Any]) -> dict[str, Any]:
    if svc not in SERVICES and svc != "routing":
        raise ValueError(f"unknown service '{svc}'")
    data = _load()
    current = data.get(svc, {})
    for k, v in fields.items():
        # Don't wipe a stored secret when the field is left blank.
        if k in SECRET_FIELDS and (v is None or v == ""):
            continue
        if v is not None:
            current[k] = v
    data[svc] = current
    _save(data)
    return public_view()[svc] if svc != "routing" else {"routing": current}


def test(svc: str) -> dict[str, Any]:
    """Ping a service with its configured URL + token."""
    if stack_config is None:
        return {"ok": False, "detail": "stack connectors not available in this build"}
    import requests  # lazy: keep the core API importable even if requests is absent

    try:
        if svc == "paperless":
            c = stack_config.paperless()
            r = requests.get(f"{c.base_url}/api/", headers={"Authorization": f"Token {c.token}"},
                             timeout=10)
        elif svc == "firefly":
            c = stack_config.firefly()
            r = requests.get(f"{c.base_url}/api/v1/about",
                             headers={"Authorization": f"Bearer {c.token}", "Accept": "application/json"},
                             timeout=10)
        elif svc == "strapi":
            c = stack_config.strapi()
            r = requests.get(f"{c.base_url}/api/transactions",
                             headers={"Authorization": f"Bearer {c.token}"},
                             params={"pagination[pageSize]": 1}, timeout=10)
        elif svc == "akaunting":
            c = stack_config.akaunting()
            headers = {"Accept": "application/json"}
            auth = None
            if c.token:
                headers["Authorization"] = f"Bearer {c.token}"
            elif c.extra.get("email"):
                auth = (c.extra["email"], c.extra["password"])
            r = requests.get(f"{c.base_url}/api/companies", headers=headers, auth=auth,
                             params={"company_id": c.extra["company_id"]}, timeout=10)
        else:
            return {"ok": False, "detail": f"unknown service {svc}"}
    except requests.RequestException as exc:
        return {"ok": False, "detail": f"could not reach service: {exc}"}

    ok = r.status_code < 400
    return {
        "ok": ok,
        "status_code": r.status_code,
        "detail": "connected" if ok else f"HTTP {r.status_code}: {r.text[:160]}",
    }
