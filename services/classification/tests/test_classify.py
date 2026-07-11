"""Classification service tests (MediaPipe / EfficientNet-Lite0).

The service cannot boot without the model weights, so the whole module skips
when they haven't been downloaded (see the README's curl command); the Docker
image always ships them.
"""

import io
from pathlib import Path

import pytest

MODEL = Path(__file__).resolve().parents[1] / "models" / "efficientnet_lite0.tflite"
if not MODEL.exists():
    pytest.skip("model file not downloaded", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.classifier import MediaPipeClassifier  # noqa: E402
from app.main import app  # noqa: E402


def _png(color=(200, 120, 30), size=(224, 224)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_classify_endpoint_returns_valid_result():
    with TestClient(app) as c:
        r = c.post("/classify", files={"image": ("a.png", _png(), "image/png")})
        assert r.status_code == 200
        body = r.json()
        assert body["category"]  # a non-empty ImageNet label
        assert 0.0 <= body["confidence"] <= 1.0


def test_empty_image_rejected():
    with TestClient(app) as c:
        assert c.post("/classify", files={"image": ("e.png", b"", "image/png")}).status_code == 422


def test_health():
    with TestClient(app) as c:
        assert c.get("/health").json()["service"] == "classification"


def test_handles_small_and_large_images():
    clf = MediaPipeClassifier(str(MODEL))
    assert clf.classify(_png(size=(32, 32))).category
    assert clf.classify(_png(size=(1024, 768))).category


def test_picks_highest_confidence_category():
    """The result must be the max-confidence category, whatever order the
    model returns them in."""
    import threading
    from types import SimpleNamespace

    import mediapipe as mp

    clf = MediaPipeClassifier.__new__(MediaPipeClassifier)
    clf._mp = mp
    clf._lock = threading.Lock()
    cats = [
        SimpleNamespace(category_name="lampshade", score=0.11),
        SimpleNamespace(category_name="studio couch", score=0.62),
        SimpleNamespace(category_name="quilt", score=0.31),
    ]
    clf._classifier = SimpleNamespace(
        classify=lambda img: SimpleNamespace(
            classifications=[SimpleNamespace(categories=cats)]
        )
    )
    res = clf.classify(_png())
    assert res.category == "studio couch"
    assert res.confidence == 0.62
