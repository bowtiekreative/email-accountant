"""Configuration for the self-hosted stack connectors.

Values come from a UI-writable JSON file first
(``$EMAIL_ACCOUNTANT_HOME/stack_config.json``), then environment variables as a
fallback. So you can configure links/tokens in the dashboard's Connections page
OR via .env.stack — whichever you set wins (file overrides env per-field).
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILE = Path(
    os.environ.get("EMAIL_ACCOUNTANT_HOME", str(Path.home() / ".email-accountant"))
) / "stack_config.json"


def _file() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _val(service: str, key: str, env_key: str, default: str = "") -> str:
    data = _file().get(service, {})
    v = data.get(key)
    if v not in (None, ""):
        return str(v)
    return os.environ.get(env_key, default)


def _enabled(service: str, env_key: str) -> bool:
    data = _file().get(service, {})
    if "enabled" in data:
        return bool(data["enabled"])
    return os.environ.get(env_key, "true").lower() in ("1", "true", "yes")


@dataclass
class ServiceConfig:
    base_url: str
    token: str
    enabled: bool
    extra: dict


def paperless() -> ServiceConfig:
    return ServiceConfig(
        base_url=_val("paperless", "url", "PAPERLESS_URL", "http://localhost:8080").rstrip("/"),
        token=_val("paperless", "token", "PAPERLESS_TOKEN"),
        enabled=_enabled("paperless", "PAPERLESS_ENABLED"),
        extra={},
    )


def akaunting() -> ServiceConfig:
    return ServiceConfig(
        base_url=_val("akaunting", "url", "AKAUNTING_URL", "http://localhost:8010").rstrip("/"),
        token=_val("akaunting", "token", "AKAUNTING_TOKEN"),
        enabled=_enabled("akaunting", "AKAUNTING_ENABLED"),
        extra={
            "company_id": _val("akaunting", "company_id", "AKAUNTING_COMPANY_ID", "1"),
            "email": _val("akaunting", "email", "AKAUNTING_EMAIL"),
            "password": _val("akaunting", "password", "AKAUNTING_PASSWORD"),
            "bank_account_id": _val("akaunting", "account_id", "AKAUNTING_ACCOUNT_ID", "1"),
        },
    )


def firefly() -> ServiceConfig:
    return ServiceConfig(
        base_url=_val("firefly", "url", "FIREFLY_URL", "http://localhost:8020").rstrip("/"),
        token=_val("firefly", "token", "FIREFLY_TOKEN"),
        enabled=_enabled("firefly", "FIREFLY_ENABLED"),
        extra={
            "asset_account": _val("firefly", "asset_account", "FIREFLY_ASSET_ACCOUNT", "Checking account"),
            "revenue_account": _val("firefly", "revenue_account", "FIREFLY_REVENUE_ACCOUNT", "Income"),
        },
    )


def strapi() -> ServiceConfig:
    return ServiceConfig(
        base_url=_val("strapi", "url", "STRAPI_URL", "http://localhost:1337").rstrip("/"),
        token=_val("strapi", "token", "STRAPI_TOKEN"),
        enabled=_enabled("strapi", "STRAPI_ENABLED"),
        extra={},
    )


def routing() -> dict:
    rules = _file().get("routing", {})
    return {
        "business": rules.get("business") or os.environ.get("ROUTE_BUSINESS", "akaunting"),
        "personal": rules.get("personal") or os.environ.get("ROUTE_PERSONAL", "firefly"),
        "unknown": rules.get("unknown") or os.environ.get("ROUTE_UNKNOWN", "firefly"),
        "documents": rules.get("documents") or os.environ.get("ROUTE_DOCUMENTS", "paperless"),
    }
