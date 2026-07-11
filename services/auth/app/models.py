from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from app.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """User table owned by the Auth service.

    Columns come from fastapi-users: id (UUID pk), email (unique, indexed),
    hashed_password, is_active, is_superuser, is_verified.
    """

    pass
