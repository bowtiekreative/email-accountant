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
_procs: dict[str, subprocess.Popen] = {}  # job_id -> process (not JSON-returned)
_lock = threading.Lock()

# Full-history backfills can take a long time; give them a generous ceiling.
_TIMEOUTS = {"incremental": 60 * 30, "full": 60 * 60 * 6}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(job_id: str) -> None:
    job = _jobs[job_id]
    try:
        proc = subprocess.Popen(
            shlex.split(job["command"]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _procs[job_id] = proc
        try:
            out, err = proc.communicate(timeout=_TIMEOUTS.get(job["mode"], 60 * 30))
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            with _lock:
                job["status"] = "failed"
                job["error"] = "Scan timed out"
                job["finished_at"] = _now()
            return
        with _lock:
            if job.get("status") == "stopped":
                pass  # user stopped it; keep that status
            else:
                job["status"] = "completed" if proc.returncode == 0 else "failed"
            job["return_code"] = proc.returncode
            job["output"] = (out or "")[-8000:]
            job["error"] = (err or "")[-4000:]
            job["finished_at"] = _now()
    except Exception as exc:  # noqa: BLE001 - surface any launch failure to the UI
        with _lock:
            job["status"] = "failed"
            job["error"] = f"{type(exc).__name__}: {exc}"
            job["finished_at"] = _now()
    finally:
        _procs.pop(job_id, None)


def stop_scan() -> dict[str, Any]:
    """Stop the currently running scan, if any."""
    with _lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
    if not running:
        return {"stopped": False, "reason": "no scan running"}
    job = running[0]
    proc = _procs.get(job["id"])
    with _lock:
        job["status"] = "stopped"
        job["finished_at"] = _now()
    if proc and proc.poll() is None:
        proc.terminate()
    return {"stopped": True, "id": job["id"]}


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
