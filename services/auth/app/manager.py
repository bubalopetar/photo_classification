import logging
import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_async_session
from app.models import User
from app.schemas import UserCreate

logger = logging.getLogger("auth")

MIN_PASSWORD_LENGTH = 8


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret
    verification_token_secret = settings.secret

    async def validate_password(self, password: str, user: UserCreate | User) -> None:
        # Enforced by fastapi-users on register, password reset, and user
        # update — every path that can set a password.
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidPasswordException(
                reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
            )
        if user.email.lower() in password.lower():
            raise InvalidPasswordException(reason="Password must not contain your e-mail address")

    async def on_after_register(self, user: User, request: Request | None = None):
        logger.info("user registered: %s", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info("password reset requested: %s", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ):
        logger.info("verification requested: %s", user.id)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
