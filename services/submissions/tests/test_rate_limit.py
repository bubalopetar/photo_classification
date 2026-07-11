import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app

# Per-test limiter reset lives in conftest.py (_fresh_rate_limits, autouse).


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 30, 200)).save(buf, "PNG")
    return buf.getvalue()


def _meta() -> dict:
    return {
        "name": "Ann",
        "age": "30",
        "place_of_living": "Zagreb",
        "gender": "female",
        "country_of_origin": "Croatia",
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_upload_rate_limited(monkeypatch, client, token):
    monkeypatch.setattr(settings, "upload_rate_limit", 2)
    t = token()
    for _ in range(2):
        r = client.post(
            "/submissions",
            headers=_auth(t),
            files={"image": ("p.png", _png(), "image/png")},
            data=_meta(),
        )
        assert r.status_code == 201, r.text
    r = client.post(
        "/submissions",
        headers=_auth(t),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_upload_within_limit_unaffected(client, token):
    r = client.post(
        "/submissions",
        headers=_auth(token()),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    assert r.status_code == 201, r.text
