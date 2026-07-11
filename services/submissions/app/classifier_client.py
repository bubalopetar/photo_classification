"""Synchronous call to the Classification service.

This is the one cross-service business call in the platform: on upload,
Submissions asks Classification for a result and waits for it, so the response
carries the classification immediately.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas import ClassificationResult


class ClassificationError(Exception):
    pass


async def classify(data: bytes, content_type: str) -> ClassificationResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.classification_url}/classify",
                files={"image": ("upload", data, content_type)},
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ClassificationError(str(exc)) from exc
    return ClassificationResult.model_validate(resp.json())
