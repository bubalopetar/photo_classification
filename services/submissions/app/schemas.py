import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Cross-service contract for the Submissions -> Classification call; shared so
# both sides always agree on the shape (see libs/shared/shared/contracts.py).
from shared.contracts import ClassificationResult

__all__ = [
    "ClassificationResult",
    "Gender",
    "SubmissionMetadata",
    "SubmissionRead",
]


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class SubmissionMetadata(BaseModel):
    """Validated metadata accompanying an upload.

    Bounds (age range, string lengths, gender enum) are a first line of input
    validation — see the safety notes in the README.
    """

    name: str = Field(min_length=1, max_length=200)
    age: int = Field(ge=0, le=120)
    place_of_living: str = Field(min_length=1, max_length=200)
    gender: Gender
    country_of_origin: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None
    name: str
    age: int
    place_of_living: str
    gender: str
    country_of_origin: str
    description: str | None
    photo_key: str
    photo_content_type: str
    classification: dict
    created_at: datetime
    updated_at: datetime
