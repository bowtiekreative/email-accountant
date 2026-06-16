"""Shared test setup: put repo root and the webapp backend on sys.path, and
point the ledger at a temporary directory so tests never touch real data."""
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "webapp" / "backend"))

# Isolated, throwaway ledger directory for the whole test session.
_TMP = tempfile.mkdtemp(prefix="ea_tests_")
os.environ["EMAIL_ACCOUNTANT_DB_DIR"] = _TMP
