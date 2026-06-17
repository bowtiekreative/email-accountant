"""Paperless-ngx connector — uploads receipt/invoice attachments for OCR + archive."""

import os
from typing import Any, Optional

from . import config
from ._http import request


def _headers(cfg) -> dict:
    return {"Authorization": f"Token {cfg.token}"}


def available() -> bool:
    cfg = config.paperless()
    return cfg.enabled and bool(cfg.token)


def upload_document(path: str, title: Optional[str] = None,
                    created: Optional[str] = None,
                    tags: Optional[list[str]] = None) -> dict[str, Any]:
    """Upload a file to Paperless. Returns the consumption task id.

    Paperless OCRs and files it asynchronously; the returned task id can be
    polled, but for our purposes recording it is enough.
    """
    cfg = config.paperless()
    if not available():
        return {"skipped": "paperless disabled or no token"}
    if not os.path.exists(path):
        return {"skipped": f"file not found: {path}"}

    data: dict[str, Any] = {}
    if title:
        data["title"] = title
    if created:
        data["created"] = created
    # Tags must be existing tag IDs in Paperless; we pass names via title/notes
    # instead to avoid a lookup round-trip. (Tag automation is configured in
    # Paperless itself.)
    with open(path, "rb") as fh:
        files = {"document": (os.path.basename(path), fh)}
        task = request(
            "POST", f"{cfg.base_url}/api/documents/post_document/",
            headers=_headers(cfg), data=data, files=files,
        )
    return {"task_id": task if isinstance(task, str) else task, "uploaded": True}
