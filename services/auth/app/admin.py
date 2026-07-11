from fastapi_users.password import PasswordHelper
from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request
from wtforms import PasswordField

from app.db import async_session_maker
from app.models import User

password_helper = PasswordHelper()


class AdminAuth(AuthenticationBackend):
    """Gate sqladmin behind the same user table as fastapi-users.

    Only active superusers can log in; passwords are verified with the same
    hasher fastapi-users uses, so credentials stay in sync.
    """

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email, password = form["username"], str(form["password"])
        async with async_session_maker() as session:
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
        if not user or not user.is_active or not user.is_superuser:
            return False
        verified, _ = password_helper.verify_and_update(password, user.hashed_password)
        if not verified:
            return False
        request.session.update({"admin_user": str(user.id)})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "admin_user" in request.session


class UserAdmin(ModelView, model=User):
    column_list = ["id", "email", "is_active", "is_superuser", "is_verified"]
    column_searchable_list = ["email"]
    column_details_exclude_list = ["hashed_password"]
    form_excluded_columns = ["hashed_password"]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules)
        form_class.password = PasswordField("Password")
        return form_class

    async def on_model_change(
        self, data: dict, model: User, is_created: bool, request: Request
    ) -> None:
        password = data.pop("password", None)
        if password:
            model.hashed_password = password_helper.hash(password)
        elif is_created:
            raise ValueError("Password is required when creating a user.")
