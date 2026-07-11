"""Manually create or promote a superuser.

Usage: python create_superuser.py <email> <password>

Startup bootstrap (ADMIN_EMAIL / ADMIN_PASSWORD) is the usual path; this script
is for ad-hoc promotion.
"""

import asyncio
import sys

from sqlalchemy import select

from app.admin import password_helper
from app.db import async_session_maker, create_db_and_tables
from app.models import User


async def main(email: str, password: str) -> None:
    await create_db_and_tables()
    async with async_session_maker() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    email=email,
                    hashed_password=password_helper.hash(password),
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                )
            )
            action = "created"
        else:
            user.hashed_password = password_helper.hash(password)
            user.is_active = user.is_superuser = user.is_verified = True
            action = "promoted"
        await session.commit()
    print(f"Superuser {action}: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_superuser.py <email> <password>")
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
