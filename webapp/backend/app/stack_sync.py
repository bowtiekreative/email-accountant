"""Run sync_to_stack.py (route ledger → stack) as a background job from the UI."""

import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
_state: dict[str, Any] = {"status": "idle", "output": "", "finished_at": None}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(force: bool) -> None:
    cmd = [sys.executable, str(_REPO_ROOT / "sync_to_stack.py")]
    if force:
        cmd.append("--force")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 60,
                              cwd=str(_REPO_ROOT))
        with _lock:
            _state["status"] = "completed" if proc.returncode == 0 else "failed"
            _state["output"] = ((proc.stdout or "") + (proc.stderr or ""))[-8000:]
            _state["finished_at"] = _now()
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _state["status"] = "failed"
            _state["output"] = f"{type(exc).__name__}: {exc}"
            _state["finished_at"] = _now()


def start(force: bool = False) -> dict[str, Any]:
    with _lock:
        if _state["status"] == "running":
            return {"already_running": True, **_state}
        _state.update(status="running", output="", started_at=_now(), finished_at=None)
    threading.Thread(target=_run, args=(force,), daemon=True).start()
    return dict(_state)


def status() -> dict[str, Any]:
    return dict(_state)
