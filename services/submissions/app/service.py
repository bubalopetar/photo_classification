"""Core submission workflow, shared by the JSON API and the browser form.

Sequence: validate + clean the image (safety gate) -> classify -> reject if
unsafe -> store the photo -> persist the row. The photo is only written and the
row only created once the content is confirmed safe.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import classifier_client, safety, storage
from app.models import Submission
from app.schemas import SubmissionMetadata


class UnsafeContent(Exception):
    """Classification flagged the image; the upload is refused."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons) or "unsafe content")


async def create_submission(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    meta: SubmissionMetadata,
    raw_bytes: bytes,
    user_email: str | None = None,
) -> Submission:
    # 1. Safety gate (raises safety.UnsafeUpload on bad input).
    clean_bytes, content_type = safety.validate_and_clean(raw_bytes)

    # 2. Classify (raises classifier_client.ClassificationError if unreachable).
    result = await classifier_client.classify(clean_bytes, content_type)

    # 3. Content-safety verdict.
    if not result.safe:
        raise UnsafeContent(result.reasons)

    # 4. Store the (cleaned) photo, then 5. persist the record.
    key = storage.new_key(content_type)
    storage.storage.put(key, clean_bytes, content_type)

    submission = Submission(
        user_id=user_id,
        user_email=user_email,
        name=meta.name,
        age=meta.age,
        place_of_living=meta.place_of_living,
        gender=meta.gender.value,
        country_of_origin=meta.country_of_origin,
        description=meta.description,
        photo_key=key,
        photo_content_type=content_type,
        classification=result.model_dump(),
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)
    return submission


async def delete_submission(session: AsyncSession, submission: Submission) -> None:
    """Remove the row, then the photo. Row first: a leftover object in storage
    is harmless, a surviving row pointing at deleted bytes is not."""
    photo_key = submission.photo_key
    await session.delete(submission)
    await session.commit()
    storage.storage.delete(photo_key)
