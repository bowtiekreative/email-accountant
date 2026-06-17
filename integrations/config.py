"""Configuration for the self-hosted stack connectors.

Everything is environment-driven so the same code works against local Docker
services or remote hosts. See .env.stack.example.
"""

import os
from dataclasses import dataclass


@dataclass
class ServiceConfig:
    base_url: str
    token: str
    enabled: bool
    extra: dict


def _svc(prefix: str, default_url: str) -> ServiceConfig:
    base = os.environ.get(f"{prefix}_URL", default_url).rstrip("/")
    token = os.environ.get(f"{prefix}_TOKEN", "")
    enabled = os.environ.get(f"{prefix}_ENABLED", "true").lower() in ("1", "true", "yes")
    return ServiceConfig(base_url=base, token=token, enabled=enabled, extra={})


def paperless() -> ServiceConfig:
    return _svc("PAPERLESS", "http://localhost:8000")


def akaunting() -> ServiceConfig:
    cfg = _svc("AKAUNTING", "http://localhost:8010")
    cfg.extra["company_id"] = os.environ.get("AKAUNTING_COMPANY_ID", "1")
    # Akaunting uses basic auth (email + password) or a token, depending on setup.
    cfg.extra["email"] = os.environ.get("AKAUNTING_EMAIL", "")
    cfg.extra["password"] = os.environ.get("AKAUNTING_PASSWORD", "")
    cfg.extra["bank_account_id"] = os.environ.get("AKAUNTING_ACCOUNT_ID", "1")
    return cfg


def firefly() -> ServiceConfig:
    cfg = _svc("FIREFLY", "http://localhost:8020")
    cfg.extra["asset_account"] = os.environ.get("FIREFLY_ASSET_ACCOUNT", "Checking account")
    cfg.extra["revenue_account"] = os.environ.get("FIREFLY_REVENUE_ACCOUNT", "Income")
    return cfg


def strapi() -> ServiceConfig:
    return _svc("STRAPI", "http://localhost:1337")


# How transactions route by domain. Strapi can override this at runtime.
def routing() -> dict:
    return {
        "business": os.environ.get("ROUTE_BUSINESS", "akaunting"),
        "personal": os.environ.get("ROUTE_PERSONAL", "firefly"),
        "unknown": os.environ.get("ROUTE_UNKNOWN", "firefly"),
        # Always send attachments to Paperless when present.
        "documents": os.environ.get("ROUTE_DOCUMENTS", "paperless"),
    }
