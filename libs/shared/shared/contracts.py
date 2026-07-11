"""Cross-service API contracts.

The ONE schema deliberately shared between services: the classification
result. Both sides of the Submissions -> Classification call must agree on it,
so it lives here instead of being defined twice. Everything else (models,
request schemas) stays private to its owning service.
"""

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Result returned by the Classification service for one image.

    `safe` is the content-safety verdict: Submissions rejects an upload when it
    is False. `reasons` explains a rejection (empty when safe).
    """

    category: str = Field(examples=["portrait", "landscape", "animal"])
    confidence: float = Field(ge=0.0, le=1.0, examples=[0.92])
    safe: bool = True
    reasons: list[str] = Field(default_factory=list)
