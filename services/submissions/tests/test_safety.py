import io

import pytest
from PIL import Image

from app.safety import UnsafeUpload, validate_and_clean


def _img(fmt: str, size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, fmt)
    return buf.getvalue()


def test_accepts_png_and_reports_type():
    cleaned, ctype = validate_and_clean(_img("PNG"))
    assert ctype == "image/png"
    assert cleaned  # re-encoded bytes


def test_accepts_jpeg():
    _, ctype = validate_and_clean(_img("JPEG"))
    assert ctype == "image/jpeg"


def test_rejects_empty():
    with pytest.raises(UnsafeUpload):
        validate_and_clean(b"")


def test_rejects_non_image():
    with pytest.raises(UnsafeUpload):
        validate_and_clean(b"this is definitely not an image")


def test_rejects_spoofed_content():
    # Bytes that are not a real image signature are rejected regardless of any
    # client-declared content type.
    with pytest.raises(UnsafeUpload):
        validate_and_clean(b"GIF89a-but-truncated-and-fake")


def test_strips_exif():
    # Build a JPEG carrying EXIF, confirm the cleaned output drops it.
    from PIL import Image as PImage

    src = PImage.new("RGB", (32, 32), (1, 2, 3))
    buf = io.BytesIO()
    exif = src.getexif()
    exif[0x010F] = "SecretCameraMake"
    src.save(buf, "JPEG", exif=exif)
    assert b"SecretCameraMake" in buf.getvalue()

    cleaned, _ = validate_and_clean(buf.getvalue())
    assert b"SecretCameraMake" not in cleaned
