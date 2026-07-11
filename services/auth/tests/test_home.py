"""Home page: welcome card plus the inline submissions panel.

The submissions data comes from a server-side call to the Submissions
service; these tests stub that call so they exercise both the populated
panel and the graceful-degradation path without a live service.
"""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app


def _login(c: TestClient) -> None:
    c.post("/auth/register", json={"email": "homer@test.io", "password": "secret123"})
    c.post("/login", data={"email": "homer@test.io", "password": "secret123"})


def test_home_renders_submissions_inline(monkeypatch):
    async def fake_fetch(token):
        return [
            {
                "id": str(uuid.uuid4()),
                "name": "Ana",
                "age": 30,
                "place_of_living": "Zagreb",
                "country_of_origin": "Croatia",
                "classification": {"category": "portrait", "confidence": 0.92},
                "created_at": datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            }
        ]

    monkeypatch.setattr("app.main.fetch_my_submissions", fake_fetch)
    with TestClient(app) as c:
        _login(c)
        r = c.get("/")
        assert r.status_code == 200
        assert "Welcome" in r.text
        assert "My submissions" in r.text
        assert "Ana" in r.text
        assert "92% confidence" in r.text


def test_home_degrades_when_submissions_unavailable(monkeypatch):
    async def fake_fetch(token):
        return None

    monkeypatch.setattr("app.main.fetch_my_submissions", fake_fetch)
    with TestClient(app) as c:
        _login(c)
        r = c.get("/")
        assert r.status_code == 200
        assert "Welcome" in r.text
        assert "Couldn't load your submissions" in r.text


def test_home_empty_state(monkeypatch):
    async def fake_fetch(token):
        return []

    monkeypatch.setattr("app.main.fetch_my_submissions", fake_fetch)
    with TestClient(app) as c:
        _login(c)
        r = c.get("/")
        assert r.status_code == 200
        assert "No submissions yet" in r.text
