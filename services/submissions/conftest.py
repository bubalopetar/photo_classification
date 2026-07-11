"""Pytest bootstrap for the Submissions service.

Paths + a throwaway SQLite DB and local storage dir, set before `app` imports.
"""

import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest

_SERVICE = Path(__file__).resolve().parent
_ROOT = _SERVICE.parents[1]

sys.path.insert(0, str(_ROOT / "libs" / "shared"))
sys.path.insert(0, str(_SERVICE))

os.environ.setdefault("SECRET", "test-secret-value-at-least-32-chars-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_submissions.db")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./test_uploads")
# CORS middleware is attached at app-import time, so the test origin must be
# configured here rather than monkeypatched per test (see tests/test_cors.py).
os.environ.setdefault("CORS_ALLOW_ORIGINS", "https://cors-test.example")

for _p in (_SERVICE / "test_submissions.db",):
    if _p.exists():
        _p.unlink()
_uploads = _SERVICE / "test_uploads"
if _uploads.exists():
    shutil.rmtree(_uploads)


@pytest.fixture(autouse=True)
def _isolate_db():
    """Clear the submission table after each test so rows don't leak between
    tests (they all share one SQLite file). Runs after the TestClient — and thus
    the async engine's connections — has been torn down, so no lock contention.
    """
    yield
    import sqlite3

    db = _SERVICE / "test_submissions.db"
    if db.exists():
        con = sqlite3.connect(db)
        try:
            con.execute("DELETE FROM submission")
            con.commit()
        except sqlite3.OperationalError:
            pass  # table not created yet (test never opened the app)
        finally:
            con.close()


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """The rate limiter is process-wide state; without a per-test reset the
    per-IP budgets would accumulate across the whole session (every test
    shares the 'testclient' IP)."""
    from app.limits import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def token():
    """Mint tokens exactly as Auth would, without running Auth."""
    from app.config import settings
    from shared.security import encode_token

    def _make(*, is_superuser: bool = False, email: str = "u@test.io") -> str:
        return encode_token(
            user_id=uuid.uuid4(),
            secret=settings.secret,
            audience=settings.jwt_audience,
            lifetime_seconds=3600,
            email=email,
            is_superuser=is_superuser,
        )

    return _make


@pytest.fixture
def set_classifier(monkeypatch):
    """Replace the cross-service classify call with a canned result."""
    from app.schemas import ClassificationResult

    def _apply(result: ClassificationResult):
        async def fake(data: bytes, content_type: str) -> ClassificationResult:
            return result

        import app.classifier_client as cc
        import app.service as svc

        monkeypatch.setattr(cc, "classify", fake)
        monkeypatch.setattr(svc.classifier_client, "classify", fake)

    return _apply


@pytest.fixture(autouse=True)
def safe_classifier(set_classifier):
    """Default: every upload is classified safe unless a test overrides it."""
    from app.schemas import ClassificationResult

    set_classifier(ClassificationResult(category="portrait", confidence=0.9, safe=True))
