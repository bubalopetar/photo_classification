"""In-memory sliding-window rate limiting for abuse-prone endpoints.

Deliberately dependency-free. Each service creates one `SlidingWindowLimiter`
and attaches `rate_limit(...)` dependencies to the endpoints worth protecting
(login, register, upload). State is per-process: with several replicas behind
a load balancer each pod enforces its own budget, so the effective global
limit is N_replicas x limit — good enough for brute-force/abuse damping. If
exact cluster-wide limits are ever needed, a Redis-backed limiter can
implement the same `hit` contract and drop in here.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    """Tracks request timestamps per key; the clock is injectable for tests."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, *, max_requests: int, window_seconds: float) -> float | None:
        """Record one request for `key` if capacity allows.

        Returns None when the request is allowed, otherwise the seconds until
        capacity frees up. Rejected requests are NOT recorded, so a client
        hammering a limited endpoint doesn't extend its own lockout.
        """
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        cutoff = now - window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= max_requests:
            return hits[0] + window_seconds - now
        hits.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    """Rate-limit key for a request: the calling client's IP.

    Honors the first hop of X-Forwarded-For because in Docker/Kubernetes the
    services sit behind an ingress/proxy that sets it. If a service were ever
    exposed directly, this header is client-controlled and the ingress should
    be configured to overwrite it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    scope: str,
    *,
    limiter: SlidingWindowLimiter,
    max_requests: Callable[[], int],
    window_seconds: Callable[[], float],
    enabled: Callable[[], bool] = lambda: True,
):
    """Build a FastAPI dependency enforcing `max_requests` per client IP per
    window on every route it's attached to.

    Routes sharing a `scope` share one budget — e.g. the JSON and browser
    login endpoints must drain the same bucket, or the limit is trivially
    bypassed by alternating between them. The limits are read through
    callables at request time so settings changes (and test monkeypatching)
    take effect without an app restart.
    """

    async def dependency(request: Request) -> None:
        if not enabled():
            return
        retry_after = limiter.hit(
            f"{scope}:{client_ip(request)}",
            max_requests=max_requests(),
            window_seconds=window_seconds(),
        )
        if retry_after is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(math.ceil(retry_after))},
            )

    return dependency
