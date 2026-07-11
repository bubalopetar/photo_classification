from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.config import BaseServiceSettings
from shared.cors import add_cors

ALLOWED = "https://app.example"
OTHER = "https://evil.example"


def _app(origins: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    add_cors(app, origins)
    return app


def test_no_origins_configured_means_no_cors_headers():
    with TestClient(_app([])) as c:
        r = c.get("/ping", headers={"Origin": OTHER})
        assert r.status_code == 200
        assert "access-control-allow-origin" not in r.headers


def test_allowed_origin_gets_cors_headers_with_credentials():
    with TestClient(_app([ALLOWED])) as c:
        r = c.get("/ping", headers={"Origin": ALLOWED})
        assert r.headers["access-control-allow-origin"] == ALLOWED
        assert r.headers["access-control-allow-credentials"] == "true"


def test_disallowed_origin_gets_no_allow_header():
    with TestClient(_app([ALLOWED])) as c:
        r = c.get("/ping", headers={"Origin": OTHER})
        assert "access-control-allow-origin" not in r.headers


def test_preflight_succeeds_for_allowed_origin():
    with TestClient(_app([ALLOWED])) as c:
        r = c.options(
            "/ping",
            headers={"Origin": ALLOWED, "Access-Control-Request-Method": "GET"},
        )
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == ALLOWED


def test_settings_parse_comma_separated_origins():
    s = BaseServiceSettings(
        secret="x", cors_allow_origins=" https://a.example, https://b.example ,"
    )
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_settings_default_is_no_origins():
    s = BaseServiceSettings(secret="x")
    assert s.cors_origins == []
