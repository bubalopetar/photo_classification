"""Optional first-run superuser provisioning.

If ADMIN_EMAIL and ADMIN_PASSWORD are set, ensure a matching active, verified
superuser exists (create or promote). Runs on startup so a fresh deployment has
an admin who can reach the admin panel. Safe to run repeatedly.
"""

import logging

from sqlalchemy import select

from app.admin import password_helper
from app.config import settings
from app.db import async_session_maker
from app.models import User

logger = logging.getLogger("auth")


async def ensure_superuser() -> None:
    if not settings.admin_email or not settings.admin_password:
        return
    async with async_session_maker() as session:
        user = (
            await session.execute(
                select(User).where(User.email == settings.admin_email)
            )
        ).scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    email=settings.admin_email,
                    hashed_password=password_helper.hash(settings.admin_password),
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                )
            )
            action = "created"
        else:
            user.hashed_password = password_helper.hash(settings.admin_password)
            user.is_active = True
            user.is_superuser = True
            user.is_verified = True
            action = "promoted"
        await session.commit()
    logger.info("bootstrap superuser %s: %s", action, settings.admin_email)
