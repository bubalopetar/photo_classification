"""Server-side fetch of the caller's submissions from the Submissions service.

The home page renders the user's submissions inline. Auth forwards the
caller's own JWT as a bearer token, so Submissions applies its normal
authorization. Any failure degrades to "couldn't load" on the home page
rather than breaking it.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

# Public URL of the Submissions service, used for browser-facing links and
# photo thumbnails on the home page. Defaults to the local dev port.
SUBMISSIONS_PUBLIC_URL = os.getenv("SUBMISSIONS_PUBLIC_URL", "http://localhost:8002")

# URL for the server-side call (in-cluster address under docker-compose /
# Kubernetes). Falls back to the public URL, which is correct for local dev.
SUBMISSIONS_URL = os.getenv("SUBMISSIONS_URL", SUBMISSIONS_PUBLIC_URL)


async def fetch_my_submissions(token: str) -> list[dict[str, Any]] | None:
    """Return the caller's submissions (newest first), or None if unavailable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{SUBMISSIONS_URL}/submissions/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            rows = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    for row in rows:
        row["created_at"] = datetime.fromisoformat(row["created_at"])
    return rows
