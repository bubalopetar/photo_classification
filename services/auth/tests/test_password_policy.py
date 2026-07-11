from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_short_password_rejected_on_api_register():
    with _client() as c:
        r = c.post(
            "/auth/register",
            json={"email": "shorty@test.io", "password": "abc1234"},
        )
        assert r.status_code == 400, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "REGISTER_INVALID_PASSWORD"
        assert "8 characters" in detail["reason"]


def test_password_containing_email_rejected():
    with _client() as c:
        r = c.post(
            "/auth/register",
            json={"email": "carol@test.io", "password": "carol@test.io1"},
        )
        assert r.status_code == 400, r.text
        assert r.json()["detail"]["code"] == "REGISTER_INVALID_PASSWORD"


def test_short_password_rejected_on_web_register():
    with _client() as c:
        r = c.post(
            "/register",
            data={"email": "webshort@test.io", "password": "short"},
        )
        assert r.status_code == 400
        assert "Invalid password" in r.text


def test_valid_password_still_accepted():
    with _client() as c:
        r = c.post(
            "/auth/register",
            json={"email": "goodpw@test.io", "password": "longenough1"},
        )
        assert r.status_code == 201, r.text
