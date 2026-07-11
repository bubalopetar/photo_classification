"""JSON API for submissions."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import safety, service
from app.classifier_client import ClassificationError
from app.db import get_async_session
from app.limits import upload_rate_limit
from app.models import Submission
from app.schemas import Gender, SubmissionMetadata, SubmissionRead
from app.security import current_superuser, current_user, current_user_any_channel
from app.storage import storage
from shared.security import Principal

router = APIRouter(tags=["submissions"])


@router.post(
    "/submissions",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(upload_rate_limit)],
)
async def create_submission(
    image: UploadFile,
    name: str = Form(...),
    age: int = Form(...),
    place_of_living: str = Form(...),
    gender: Gender = Form(...),
    country_of_origin: str = Form(...),
    description: str | None = Form(default=None),
    principal: Principal = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Submission:
    try:
        meta = SubmissionMetadata(
            name=name,
            age=age,
            place_of_living=place_of_living,
            gender=gender,
            country_of_origin=country_of_origin,
            description=description,
        )
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()
        ) from exc
    raw = await image.read()
    try:
        return await service.create_submission(
            session,
            user_id=principal.id,
            user_email=principal.email,
            meta=meta,
            raw_bytes=raw,
        )
    except safety.UnsafeUpload as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        ) from exc
    except service.UnsafeContent as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Content rejected", "reasons": exc.reasons},
        ) from exc
    except ClassificationError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Classification service unavailable"
        ) from exc


@router.get("/submissions/me", response_model=list[SubmissionRead])
async def my_submissions(
    principal: Principal = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[Submission]:
    rows = (
        await session.execute(
            select(Submission)
            .where(Submission.user_id == principal.id)
            .order_by(Submission.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
async def get_submission(
    submission_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> Submission:
    row = await session.get(Submission, submission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if row.user_id != principal.id and not principal.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return row


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    row = await session.get(Submission, submission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if row.user_id != principal.id and not principal.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    await service.delete_submission(session, row)


@router.get("/submissions/{submission_id}/photo")
async def get_submission_photo(
    submission_id: uuid.UUID,
    # any_channel: also accepts the sqladmin session, so thumbnails render
    # inside the admin panel (browsers don't send bearer headers for <img>).
    principal: Principal = Depends(current_user_any_channel),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    row = await session.get(Submission, submission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if row.user_id != principal.id and not principal.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return Response(content=storage.get(row.photo_key), media_type=row.photo_content_type)


@router.get("/admin/submissions", response_model=list[SubmissionRead])
async def admin_list_submissions(
    principal: Principal = Depends(current_superuser),
    session: AsyncSession = Depends(get_async_session),
    gender: Gender | None = None,
    country_of_origin: str | None = None,
    place_of_living: str | None = None,
    age_min: int | None = Query(default=None, ge=0, le=120),
    age_max: int | None = Query(default=None, ge=0, le=120),
    q: str | None = Query(default=None, description="Search by name (substring)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Submission]:
    """Admin-only. Filter/search submissions by the required dimensions.

    Each filter maps to an indexed column, so these queries stay fast as the
    table grows.
    """
    stmt = select(Submission)
    if gender is not None:
        stmt = stmt.where(Submission.gender == gender.value)
    if country_of_origin is not None:
        stmt = stmt.where(Submission.country_of_origin == country_of_origin)
    if place_of_living is not None:
        stmt = stmt.where(Submission.place_of_living == place_of_living)
    if age_min is not None:
        stmt = stmt.where(Submission.age >= age_min)
    if age_max is not None:
        stmt = stmt.where(Submission.age <= age_max)
    if q:
        stmt = stmt.where(Submission.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Submission.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)
