"""Server-rendered upload screen.

Reuses the auth cookie set by the Auth service (cookies are host-scoped, shared
across localhost ports in dev). Un-authenticated visitors are redirected to
Auth's /login. The POST reuses the same `service.create_submission` workflow as
the JSON API.
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app import safety, service
from app.classifier_client import ClassificationError
from app.config import settings
from app.db import get_async_session
from app.limits import upload_rate_limit
from app.models import Submission
from app.schemas import Gender, SubmissionMetadata
from app.templating import templates
from shared.security import Principal, decode_token

router = APIRouter(tags=["submissions-web"])

_LOGIN_URL = f"{settings.auth_public_url}/login"


def _principal_or_none(token: str | None) -> Principal | None:
    if not token:
        return None
    try:
        return decode_token(
            token, secret=settings.secret, audience=settings.jwt_audience
        )
    except jwt.InvalidTokenError:
        return None


@router.get("/")
async def index():
    return RedirectResponse(url="/upload", status_code=303)


@router.get("/upload")
async def upload_get(
    request: Request,
    photoauth: str | None = Cookie(default=None),
):
    principal = _principal_or_none(photoauth)
    if principal is None:
        return RedirectResponse(url=_LOGIN_URL, status_code=303)
    return templates.TemplateResponse(
        request,
        "upload.html",
        {"genders": [g.value for g in Gender], "email": principal.email},
    )


# Shares the "upload" budget with POST /submissions: same work, same cost,
# one per-IP bucket.
@router.post("/upload", dependencies=[Depends(upload_rate_limit)])
async def upload_post(
    request: Request,
    image: UploadFile,
    name: str = Form(...),
    age: int = Form(...),
    place_of_living: str = Form(...),
    gender: str = Form(...),
    country_of_origin: str = Form(...),
    description: str = Form(default=""),
    photoauth: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_async_session),
):
    principal = _principal_or_none(photoauth)
    if principal is None:
        return RedirectResponse(url=_LOGIN_URL, status_code=303)

    ctx: dict = {"genders": [g.value for g in Gender], "email": principal.email}
    try:
        meta = SubmissionMetadata(
            name=name,
            age=age,
            place_of_living=place_of_living,
            gender=gender,
            country_of_origin=country_of_origin,
            description=description or None,
        )
        raw = await image.read()
        submission = await service.create_submission(
            session,
            user_id=principal.id,
            user_email=principal.email,
            meta=meta,
            raw_bytes=raw,
        )
    except ValidationError as exc:
        ctx["error"] = "; ".join(e["msg"] for e in exc.errors())
        return templates.TemplateResponse(request, "upload.html", ctx, status_code=400)
    except safety.UnsafeUpload as exc:
        ctx["error"] = exc.reason
        return templates.TemplateResponse(request, "upload.html", ctx, status_code=422)
    except ClassificationError:
        ctx["error"] = "Classification service is unavailable, try again."
        return templates.TemplateResponse(request, "upload.html", ctx, status_code=502)

    return templates.TemplateResponse(
        request, "result.html", {"submission": submission}
    )


@router.get("/my")
async def my_submissions_page():
    """Gone: submissions now render inline on the Auth home page."""
    return RedirectResponse(url=f"{settings.auth_public_url}/", status_code=303)


@router.post("/submissions/{submission_id}/delete")
async def delete_submission_web(
    submission_id: uuid.UUID,
    photoauth: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_async_session),
):
    """Browser form target for the delete buttons on the home page."""
    principal = _principal_or_none(photoauth)
    if principal is None:
        return RedirectResponse(url=_LOGIN_URL, status_code=303)
    row = await session.get(Submission, submission_id)
    # A vanished row means the delete already happened; just go back.
    if row is not None:
        if row.user_id != principal.id and not principal.is_superuser:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
        await service.delete_submission(session, row)
    return RedirectResponse(url=f"{settings.auth_public_url}/", status_code=303)
