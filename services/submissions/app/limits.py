"""Rate-limit dependencies for this service's abuse-prone endpoints.

One process-wide limiter; the JSON and browser upload endpoints share the
"upload" scope so both drain the same per-IP budget.
"""

from app.config import settings
from shared.ratelimit import SlidingWindowLimiter, rate_limit

limiter = SlidingWindowLimiter()

upload_rate_limit = rate_limit(
    "upload",
    limiter=limiter,
    max_requests=lambda: settings.upload_rate_limit,
    window_seconds=lambda: settings.rate_limit_window_seconds,
    enabled=lambda: settings.rate_limit_enabled,
)
