"""Browser-facing pages: delete flow, /my redirect, admin-panel photo previews."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 200, 90)).save(buf, "PNG")
    return buf.getvalue()


def _meta(**over) -> dict:
    data = {
        "name": "Mia",
        "age": "25",
        "place_of_living": "Rijeka",
        "gender": "female",
        "country_of_origin": "Croatia",
    }
    data.update(over)
    return data


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_my_redirects_to_home(client):
    """The old /my page is gone; submissions render inline on the Auth home."""
    from app.config import settings

    r = client.get("/my", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"{settings.auth_public_url}/"


def test_web_delete_removes_row_and_redirects_home(client, token):
    from app.config import settings

    t = token(email="mia@test.io")
    r = client.post(
        "/submissions",
        headers={"Authorization": f"Bearer {t}"},
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    assert r.status_code == 201
    sub_id = r.json()["id"]

    # Browser form post carries the cookie, not a bearer header.
    r = client.post(
        f"/submissions/{sub_id}/delete", cookies={"photoauth": t}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"{settings.auth_public_url}/"
    assert client.get("/submissions/me", headers={"Authorization": f"Bearer {t}"}).json() == []

    # Deleting again is idempotent from the browser's perspective.
    r = client.post(
        f"/submissions/{sub_id}/delete", cookies={"photoauth": t}, follow_redirects=False
    )
    assert r.status_code == 303


def test_web_delete_requires_login(client, token):
    t = token()
    r = client.post(
        "/submissions",
        headers={"Authorization": f"Bearer {t}"},
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]
    r = client.post(f"/submissions/{sub_id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]
    # Row untouched.
    assert len(client.get("/submissions/me", headers={"Authorization": f"Bearer {t}"}).json()) == 1


def test_photo_allows_admin_session(client, token):
    """<img> tags in the admin panel authenticate via the signed session
    cookie (which stores the admin's JWT), not a bearer header."""
    t = token()
    r = client.post(
        "/submissions",
        headers={"Authorization": f"Bearer {t}"},
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]

    # Build a signed session cookie exactly like SessionMiddleware does.
    import base64
    import json

    import itsdangerous

    from app.config import settings

    admin_jwt = token(is_superuser=True)
    payload = base64.b64encode(json.dumps({"token": admin_jwt}).encode())
    signer = itsdangerous.TimestampSigner(settings.secret)
    session_cookie = signer.sign(payload).decode()

    # Cookie name is service-specific to avoid colliding with the Auth panel's
    # session on the same host (see main.SESSION_COOKIE).
    r = client.get(
        f"/submissions/{sub_id}/photo", cookies={"submissions_session": session_cookie}
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_photo_rejects_no_credentials(client, token):
    t = token()
    r = client.post(
        "/submissions",
        headers={"Authorization": f"Bearer {t}"},
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]
    assert client.get(f"/submissions/{sub_id}/photo").status_code == 401


def test_admin_list_page_renders_thumbnail_formatter(client, token):
    """Log into the sqladmin panel via the (stubbed) Auth exchange and check
    the list AND detail pages embed <img> previews and the email link."""
    t = token()
    r = client.post(
        "/submissions",
        headers={"Authorization": f"Bearer {t}"},
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]

    # Stub the credential exchange the panel makes against the Auth service.
    import httpx

    from app import admin as admin_mod
    from app.config import settings as cfg
    from shared.security import encode_token

    admin_jwt = encode_token(
        user_id="00000000-0000-0000-0000-000000000001",
        secret=cfg.secret,
        audience=cfg.jwt_audience,
        lifetime_seconds=3600,
        email="a@t.io",
        is_superuser=True,
    )

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"access_token": admin_jwt}

    class _FakeClient:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResponse()

    original = httpx.AsyncClient
    admin_mod.httpx.AsyncClient = _FakeClient
    try:
        r = client.post(
            "/admin/login",
            data={"username": "a@t.io", "password": "x"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 303)
        r = client.get("/admin/submission/list")
        assert r.status_code == 200
        assert "<img src=\"/submissions/" in r.text  # formatter emitted a preview
        assert "/admin/user/details/" in r.text  # email links to the Users admin

        r = client.get(f"/admin/submission/details/{sub_id}")
        assert r.status_code == 200
        assert "<img src=\"/submissions/" in r.text  # large photo preview
        assert "/admin/user/details/" in r.text  # email link present here too
        assert "u@test.io" in r.text
    finally:
        admin_mod.httpx.AsyncClient = original
