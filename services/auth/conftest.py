"""Pytest bootstrap for the Auth service.

Puts the shared library and this service's package on the path, and points the
service at a throwaway SQLite database, before any test imports `app`.
"""

import os
import sys
from pathlib import Path

import pytest

_SERVICE = Path(__file__).resolve().parent
_ROOT = _SERVICE.parents[1]

sys.path.insert(0, str(_ROOT / "libs" / "shared"))
sys.path.insert(0, str(_SERVICE))

os.environ.setdefault("SECRET", "test-secret-value-at-least-32-chars-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.db")
# CORS middleware is attached at app-import time, so the test origin must be
# configured here rather than monkeypatched per test (see tests/test_cors.py).
os.environ.setdefault("CORS_ALLOW_ORIGINS", "https://cors-test.example")

# Start each run from a clean database.
_db = _SERVICE / "test_auth.db"
if _db.exists():
    _db.unlink()


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """The rate limiter is process-wide state; without a per-test reset the
    per-IP budgets would accumulate across the whole session (every test
    shares the 'testclient' IP)."""
    from app.limits import limiter

    limiter.reset()
    yield
    limiter.reset()
