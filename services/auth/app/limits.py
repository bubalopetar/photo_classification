"""Rate-limit dependencies for this service's abuse-prone endpoints.

One process-wide limiter; scopes are shared between the JSON and browser
variants of an endpoint so both drain the same per-IP budget.
"""

from app.config import settings
from shared.ratelimit import SlidingWindowLimiter, rate_limit

limiter = SlidingWindowLimiter()

login_rate_limit = rate_limit(
    "login",
    limiter=limiter,
    max_requests=lambda: settings.login_rate_limit,
    window_seconds=lambda: settings.rate_limit_window_seconds,
    enabled=lambda: settings.rate_limit_enabled,
)

register_rate_limit = rate_limit(
    "register",
    limiter=limiter,
    max_requests=lambda: settings.register_rate_limit,
    window_seconds=lambda: settings.rate_limit_window_seconds,
    enabled=lambda: settings.rate_limit_enabled,
)
