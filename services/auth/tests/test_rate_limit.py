from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# Per-test limiter reset lives in conftest.py (_fresh_rate_limits, autouse).


def _client() -> TestClient:
    return TestClient(app)


def test_login_rate_limited_after_too_many_attempts(monkeypatch):
    monkeypatch.setattr(settings, "login_rate_limit", 3)
    with _client() as c:
        for _ in range(3):
            r = c.post("/auth/jwt/login", data={"username": "x@test.io", "password": "bad"})
            assert r.status_code == 400
        r = c.post("/auth/jwt/login", data={"username": "x@test.io", "password": "bad"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers


def test_web_login_shares_the_login_bucket(monkeypatch):
    """JSON and browser login are the same attack surface: exhausting one
    must exhaust the other, or the limit is trivially bypassed."""
    monkeypatch.setattr(settings, "login_rate_limit", 3)
    with _client() as c:
        for _ in range(3):
            c.post("/auth/jwt/login", data={"username": "x@test.io", "password": "bad"})
        r = c.post("/login", data={"email": "x@test.io", "password": "bad"})
        assert r.status_code == 429


def test_register_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "register_rate_limit", 2)
    with _client() as c:
        for i in range(2):
            r = c.post(
                "/auth/register",
                json={"email": f"rl{i}@test.io", "password": "longenough1"},
            )
            assert r.status_code == 201, r.text
        r = c.post(
            "/auth/register",
            json={"email": "rl-blocked@test.io", "password": "longenough1"},
        )
        assert r.status_code == 429


def test_successful_login_within_limit_unaffected():
    with _client() as c:
        c.post("/auth/register", json={"email": "ok@test.io", "password": "longenough1"})
        r = c.post("/auth/jwt/login", data={"username": "ok@test.io", "password": "longenough1"})
        assert r.status_code == 200
