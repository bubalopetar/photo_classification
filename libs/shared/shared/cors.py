"""Deny-by-default CORS.

The platform's own UI is server-rendered from the same origin as each
service, so no cross-origin browser access is needed and none is granted:
with no origins configured (the default) the middleware isn't even
installed, and browsers block cross-origin reads. Setting
CORS_ALLOW_ORIGINS (comma-separated) opts specific origins in — the seam a
future SPA frontend would use. A wildcard is deliberately unsupported:
`allow_credentials` must be on for the cookie/JWT auth to work cross-origin,
and credentials + `*` is a combination browsers (rightly) reject.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def add_cors(app: FastAPI, origins: Sequence[str]) -> None:
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
