# The result schema is the shared cross-service contract — see
# libs/shared/shared/contracts.py. Re-exported so service code keeps importing
# from app.schemas.
from shared.contracts import ClassificationResult

__all__ = ["ClassificationResult"]
