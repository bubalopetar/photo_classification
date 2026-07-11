"""End-to-end check that main.py wires the shared CORS policy.

The conftest configures CORS_ALLOW_ORIGINS=https://cors-test.example before
the app is imported; requests from that origin must get CORS headers, any
other origin must not.
"""

from fastapi.testclient import TestClient

from app.main import app

ALLOWED = "https://cors-test.example"


def test_configured_origin_gets_cors_headers():
    with TestClient(app) as c:
        r = c.get("/health", headers={"Origin": ALLOWED})
        assert r.headers["access-control-allow-origin"] == ALLOWED
        assert r.headers["access-control-allow-credentials"] == "true"


def test_unlisted_origin_gets_no_cors_headers():
    with TestClient(app) as c:
        r = c.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers
