"""Liveness/readiness probes, identical across services.

`/health` is a liveness probe (process is up). `/ready` is a readiness probe
that runs a caller-supplied async check (e.g. DB connectivity) so Kubernetes can
withhold traffic until dependencies are reachable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response, status


def health_router(
    *,
    service: str,
    readiness_check: Callable[[], Awaitable[bool]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": service}

    @router.get("/ready")
    async def ready(response: Response) -> dict:
        if readiness_check is None:
            return {"status": "ready", "service": service}
        try:
            ok = await readiness_check()
        except Exception:
            ok = False
        if not ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not-ready", "service": service}
        return {"status": "ready", "service": service}

    return router
