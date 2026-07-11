import logging

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.classifier import MediaPipeClassifier
from app.config import settings
from app.schemas import ClassificationResult
from shared.health import health_router
from shared.logging import configure_logging

configure_logging(settings.log_level, service="classification")
logger = logging.getLogger("classification")

app = FastAPI(title="Classification Service")

# Fails fast if the model file is missing — see README for the download command.
classifier = MediaPipeClassifier(settings.model_path)
logger.info("classifier: mediapipe (%s)", settings.model_path)

app.include_router(health_router(service="classification"))


@app.post("/classify", response_model=ClassificationResult, tags=["classification"])
async def classify(image: UploadFile = File(...)) -> ClassificationResult:
    data = await image.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty image"
        )
    if len(data) > settings.max_image_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large",
        )
    # Model inference is CPU-bound; keep it off the event loop.
    return await run_in_threadpool(classifier.classify, data)
