import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db import Base


class Submission(Base):
    """A user's photo submission and its classification result.

    `user_id` references a user owned by the Auth service. Because that user
    lives in a different database (database-per-service), there is intentionally
    NO cross-database foreign key — integrity is enforced at the app layer via
    the verified JWT. `user_id` is indexed for the "my submissions" query.

    The columns the admin panel filters on (`age`, `gender`, `place_of_living`,
    `country_of_origin`) each carry a btree index; see migrations/0001.
    """

    __tablename__ = "submission"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    # Denormalized from the JWT's email claim at upload time, so the admin
    # panel can show who submitted without a cross-service call. The Auth
    # service remains the source of truth for user identity; nullable because
    # rows created before this column existed have no value.
    user_email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    age: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    place_of_living: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    # Stored as a string (validated against the Gender enum at the API layer) to
    # keep migrations portable across SQLite and Postgres.
    gender: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    country_of_origin: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Object-storage key; the bytes live in the storage layer, never the DB.
    photo_key: Mapped[str] = mapped_column(String(512), nullable=False)
    photo_content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # {category, confidence, safe} — JSON maps to JSONB-equivalent storage.
    classification: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __str__(self) -> str:  # shown in the sqladmin list
        return f"{self.name} ({self.id})"
