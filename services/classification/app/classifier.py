"""Image classifier.

`Classifier` is the seam any model implementation plugs into (a different
model, an ONNX runtime, a hosted vision API — implement `classify` and wire it
in `main.py`). The shipped implementation is Google MediaPipe's image
classifier running EfficientNet-Lite0 (ImageNet, 1000 labels) on CPU.
https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier/python
"""

from __future__ import annotations

import io
import threading
from typing import Protocol

from app.schemas import ClassificationResult


class Classifier(Protocol):
    def classify(self, image: bytes) -> ClassificationResult: ...


class MediaPipeClassifier:
    """EfficientNet-Lite0 via MediaPipe Tasks (CPU, ~20ms per image).

    The model file is downloaded at Docker build time (see Dockerfile) or via
    the curl command in the README. One classifier instance is created eagerly
    (fail fast on a missing model) and guarded by a lock: MediaPipe task objects
    are not documented as thread-safe, and FastAPI may serve requests from
    multiple worker threads.
    """

    def __init__(self, model_path: str, max_results: int = 3):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ImageClassifierOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            max_results=max_results,
        )
        self._classifier = vision.ImageClassifier.create_from_options(options)
        self._lock = threading.Lock()

    def classify(self, image: bytes) -> ClassificationResult:
        import numpy as np
        from PIL import Image

        pil = Image.open(io.BytesIO(image)).convert("RGB")
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.asarray(pil)
        )
        with self._lock:
            result = self._classifier.classify(mp_image)

        categories = result.classifications[0].categories
        if not categories:
            return ClassificationResult(category="unknown", confidence=0.0)

        top = max(categories, key=lambda c: c.score)
        return ClassificationResult(
            category=top.category_name,
            confidence=round(float(top.score), 4),
        )
