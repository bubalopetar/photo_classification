from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from shared.security import decode_token

AUD = "fastapi-users:auth"


def _client() -> TestClient:
    return TestClient(app)


def test_register_login_and_claims():
    with _client() as c:
        r = c.post(
            "/auth/register",
            json={"email": "alice@test.io", "password": "secret123"},
        )
        assert r.status_code == 201, r.text

        r = c.post(
            "/auth/jwt/login",
            data={"username": "alice@test.io", "password": "secret123"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]

        # The token carries the extra claims other services rely on.
        principal = decode_token(token, secret=settings.secret, audience=AUD)
        assert principal.email == "alice@test.io"
        assert principal.is_superuser is False


def test_me_requires_auth():
    with _client() as c:
        assert c.get("/users/me").status_code == 401


def test_browser_login_sets_cookie():
    with _client() as c:
        c.post("/auth/register", json={"email": "bob@test.io", "password": "secret123"})
        r = c.post(
            "/login",
            data={"email": "bob@test.io", "password": "secret123"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert settings.auth_cookie_name in r.cookies


def test_bad_login_rejected():
    with _client() as c:
        r = c.post(
            "/auth/jwt/login",
            data={"username": "nobody@test.io", "password": "nope"},
        )
        assert r.status_code == 400


def test_health():
    with _client() as c:
        assert c.get("/health").json()["service"] == "auth"
        assert c.get("/ready").json()["status"] == "ready"
