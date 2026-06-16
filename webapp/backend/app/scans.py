"""Trigger the existing scan pipeline from the UI as a background job.

This shells out to the repo's scan script (configurable) so we reuse the
existing Gmail scanner + categorization pipeline verbatim. Job state is kept
in memory — fine for a single-user, local-only deployment.
"""

import shlex
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import FULL_SCAN_COMMAND, SCAN_COMMAND

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()

# Full-history backfills can take a long time; give them a generous ceiling.
_TIMEOUTS = {"incremental": 60 * 30, "full": 60 * 60 * 6}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(job_id: str) -> None:
    job = _jobs[job_id]
    try:
        proc = subprocess.run(
            shlex.split(job["command"]),
            capture_output=True,
            text=True,
            timeout=_TIMEOUTS.get(job["mode"], 60 * 30),
        )
        tail = (proc.stdout or "")[-8000:]
        err = (proc.stderr or "")[-4000:]
        with _lock:
            job["status"] = "completed" if proc.returncode == 0 else "failed"
            job["return_code"] = proc.returncode
            job["output"] = tail
            job["error"] = err
            job["finished_at"] = _now()
    except subprocess.TimeoutExpired:
        with _lock:
            job["status"] = "failed"
            job["error"] = "Scan timed out"
            job["finished_at"] = _now()
    except Exception as exc:  # noqa: BLE001 - surface any launch failure to the UI
        with _lock:
            job["status"] = "failed"
            job["error"] = f"{type(exc).__name__}: {exc}"
            job["finished_at"] = _now()


def start_scan(mode: str = "incremental") -> dict[str, Any]:
    if mode not in ("incremental", "full"):
        mode = "incremental"

    # Refuse to launch a second scan while one is running.
    with _lock:
        for job in _jobs.values():
            if job["status"] == "running":
                return {"already_running": True, **job}

    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "running",
        "mode": mode,
        "command": FULL_SCAN_COMMAND if mode == "full" else SCAN_COMMAND,
        "started_at": _now(),
        "finished_at": None,
        "output": "",
        "error": "",
    }
    _jobs[job_id] = job
    threading.Thread(target=_run, args=(job_id,), daemon=True).start()
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def latest_job() -> dict[str, Any] | None:
    if not _jobs:
        return None
    return sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)[0]
