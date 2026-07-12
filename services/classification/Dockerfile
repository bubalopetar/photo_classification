# Build context is the repo root (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONPATH=/srv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# mediapipe's C bindings dlopen libGLESv2/libEGL and its opencv dependency
# needs libGL/libglib at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgles2 libegl1 && rm -rf /var/lib/apt/lists/*

COPY services/classification/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# EfficientNet-Lite0 model for the MediaPipe classifier (see app/classifier.py).
ADD https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/latest/efficientnet_lite0.tflite \
    ./models/efficientnet_lite0.tflite

COPY libs/shared/shared ./shared
COPY services/classification/app ./app

EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
