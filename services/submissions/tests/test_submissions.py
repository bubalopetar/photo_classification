import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 30, 200)).save(buf, "PNG")
    return buf.getvalue()


def _meta(**over) -> dict:
    data = {
        "name": "Ann",
        "age": "30",
        "place_of_living": "Zagreb",
        "gender": "female",
        "country_of_origin": "Croatia",
    }
    data.update(over)
    return data


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_upload_requires_auth(client):
    r = client.post("/submissions", files={"image": ("p.png", _png(), "image/png")}, data=_meta())
    assert r.status_code == 401


def test_upload_creates_submission(client, token):
    r = client.post(
        "/submissions",
        headers=_auth(token()),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(description="hello"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["classification"]["category"] == "portrait"
    assert body["gender"] == "female"
    # The submitter's email is stamped from the JWT claim at upload time.
    assert body["user_email"] == "u@test.io"


def test_non_image_rejected(client, token):
    r = client.post(
        "/submissions",
        headers=_auth(token()),
        files={"image": ("x.png", b"not an image", "image/png")},
        data=_meta(),
    )
    assert r.status_code == 422


def test_age_out_of_range_rejected(client, token):
    r = client.post(
        "/submissions",
        headers=_auth(token()),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(age="999"),
    )
    assert r.status_code == 422


def test_my_submissions_scoped_to_owner(client, token):
    t1, t2 = token(), token()
    client.post("/submissions", headers=_auth(t1), files={"image": ("p.png", _png(), "image/png")}, data=_meta())
    assert len(client.get("/submissions/me", headers=_auth(t1)).json()) == 1
    assert client.get("/submissions/me", headers=_auth(t2)).json() == []


def test_upload_survives_deleted_storage_dir(client, token):
    """The storage dir can vanish while the service runs (manual cleanup);
    put() must recreate it instead of turning every upload into a 500."""
    import shutil

    from app.config import settings as cfg

    shutil.rmtree(cfg.storage_local_dir, ignore_errors=True)
    r = client.post(
        "/submissions",
        headers=_auth(token()),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    assert r.status_code == 201, r.text


def test_delete_own_submission(client, token):
    t = token()
    r = client.post(
        "/submissions",
        headers=_auth(t),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]

    assert client.delete(f"/submissions/{sub_id}", headers=_auth(t)).status_code == 204
    assert client.get("/submissions/me", headers=_auth(t)).json() == []
    # Photo is gone with the row.
    assert client.get(f"/submissions/{sub_id}/photo", headers=_auth(t)).status_code == 404
    # Second delete: nothing left to remove.
    assert client.delete(f"/submissions/{sub_id}", headers=_auth(t)).status_code == 404


def test_delete_scoped_to_owner(client, token):
    owner, stranger, admin = token(), token(), token(is_superuser=True)
    r = client.post(
        "/submissions",
        headers=_auth(owner),
        files={"image": ("p.png", _png(), "image/png")},
        data=_meta(),
    )
    sub_id = r.json()["id"]

    assert client.delete(f"/submissions/{sub_id}").status_code == 401
    assert client.delete(f"/submissions/{sub_id}", headers=_auth(stranger)).status_code == 403
    # Still there, then a superuser may remove it.
    assert len(client.get("/submissions/me", headers=_auth(owner)).json()) == 1
    assert client.delete(f"/submissions/{sub_id}", headers=_auth(admin)).status_code == 204


def test_admin_list_requires_superuser(client, token):
    assert client.get("/admin/submissions", headers=_auth(token())).status_code == 403
    assert client.get("/admin/submissions", headers=_auth(token(is_superuser=True))).status_code == 200


def test_admin_filters(client, token):
    admin = token(is_superuser=True)
    u = token()
    client.post("/submissions", headers=_auth(u), files={"image": ("p.png", _png(), "image/png")}, data=_meta(gender="female", country_of_origin="Croatia", age="30"))
    client.post("/submissions", headers=_auth(u), files={"image": ("p.png", _png(), "image/png")}, data=_meta(gender="male", country_of_origin="Serbia", age="55"))

    assert len(client.get("/admin/submissions?gender=female", headers=_auth(admin)).json()) == 1
    assert len(client.get("/admin/submissions?country_of_origin=Serbia", headers=_auth(admin)).json()) == 1
    assert len(client.get("/admin/submissions?age_min=40&age_max=60", headers=_auth(admin)).json()) == 1
    assert len(client.get("/admin/submissions", headers=_auth(admin)).json()) == 2
