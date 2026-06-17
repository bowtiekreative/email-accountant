"""Tiny HTTP helper shared by the connectors."""

from typing import Any, Optional

import requests

TIMEOUT = 30


class ConnectorError(Exception):
    pass


def request(method: str, url: str, *, headers=None, params=None, json=None,
            data=None, files=None, auth=None) -> Any:
    try:
        resp = requests.request(
            method, url, headers=headers, params=params, json=json,
            data=data, files=files, auth=auth, timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ConnectorError(f"{method} {url} failed: {exc}") from exc
    if resp.status_code >= 400:
        raise ConnectorError(f"{method} {url} -> {resp.status_code}: {resp.text[:300]}")
    if resp.content and "application/json" in resp.headers.get("content-type", ""):
        return resp.json()
    return resp.text
