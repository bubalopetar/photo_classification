"""Admin panel over submissions (sqladmin).

Because this service does NOT own the user table, the login form exchanges the
admin's credentials with the Auth service for a JWT (one call, at login only),
then verifies the token locally and checks the `is_superuser` claim. The list
view exposes exactly the filters the assessment requires: age, gender,
place_of_living, country_of_origin.
"""

from __future__ import annotations

import httpx
import jwt
from markupsafe import Markup
from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from sqladmin.filters import (
    AllUniqueStringValuesFilter,
    OperationColumnFilter,
    StaticValuesFilter,
)
from starlette.requests import Request

from app.config import settings
from app.models import Submission
from app.schemas import Gender
from shared.security import decode_token


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email, password = str(form["username"]), str(form["password"])
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.auth_url}/auth/jwt/login",
                    data={"username": email, "password": password},
                )
        except httpx.HTTPError:
            return False
        if resp.status_code != 200:
            return False
        token = resp.json()["access_token"]
        try:
            principal = decode_token(
                token, secret=settings.secret, audience=settings.jwt_audience
            )
        except jwt.InvalidTokenError:
            return False
        if not principal.is_superuser:
            return False
        request.session.update({"token": token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        try:
            principal = decode_token(
                token, secret=settings.secret, audience=settings.jwt_audience
            )
        except jwt.InvalidTokenError:
            return False
        return principal.is_superuser


class SubmissionAdmin(ModelView, model=Submission):
    name_plural = "Submissions"
    column_list = [
        "photo_key",
        "user_email",
        "name",
        "age",
        "gender",
        "place_of_living",
        "country_of_origin",
        "classification",
        "created_at",
    ]
    column_labels = {
        "photo_key": "Photo",
        "user_email": "Submitted by",
        "user_id": "User ID",
    }
    # Render the photo columns as images. The <img> request is authorized by
    # the admin's session cookie (see security.current_user_any_channel), so
    # previews work without a separate site login. Markup keeps Jinja from
    # escaping the tag.
    @staticmethod
    def _photo(m: Submission, size_css: str) -> Markup:
        return Markup(
            f'<a href="/submissions/{m.id}/photo" target="_blank">'
            f'<img src="/submissions/{m.id}/photo" alt="photo" style="{size_css}"></a>'
        )

    # Link the submitter to their record in the Auth service's Users admin.
    # (Separate panel, separate login — sessions are isolated per service.)
    @staticmethod
    def _email_link(m: Submission) -> Markup:
        if not m.user_email:
            return Markup("<span style='opacity:.5'>—</span>")
        return Markup(
            f'<a href="{settings.auth_public_url}/admin/user/details/{m.user_id}" '
            f'target="_blank" title="Open in Users admin ({m.user_id})">{m.user_email}</a>'
        )

    column_formatters = {
        Submission.photo_key: lambda m, a: SubmissionAdmin._photo(
            m, "height:48px;width:48px;object-fit:cover;border-radius:6px"
        ),
        Submission.user_email: lambda m, a: SubmissionAdmin._email_link(m),
    }
    column_formatters_detail = {
        Submission.photo_key: lambda m, a: SubmissionAdmin._photo(
            m, "max-height:320px;max-width:100%;border-radius:8px"
        ),
        Submission.user_email: lambda m, a: SubmissionAdmin._email_link(m),
    }
    # The required admin filters — each backed by an index on the column.
    column_filters = [
        OperationColumnFilter(Submission.age, title="Age"),
        StaticValuesFilter(
            Submission.gender,
            values=[(g.value, g.value) for g in Gender],
            title="Gender",
        ),
        AllUniqueStringValuesFilter(Submission.place_of_living, title="Place of living"),
        AllUniqueStringValuesFilter(
            Submission.country_of_origin, title="Country of origin"
        ),
    ]
    column_searchable_list = ["name", "user_email", "country_of_origin", "place_of_living"]
    column_sortable_list = ["age", "created_at"]
    column_default_sort = ("created_at", True)
    can_create = False
    can_edit = False
    can_delete = True

