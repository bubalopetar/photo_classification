"""Upload safety gate.

Every uploaded file passes through here BEFORE it is stored or classified.
Layered defenses (what / why):

1. Size cap — reject oversized payloads (DoS / storage abuse).
2. Magic-byte sniffing — trust the file's real signature, not the client-sent
   Content-Type (which is trivially spoofed).
3. Allow-list of image types — only decode formats we intend to support.
4. Dimension cap — reject decompression-bomb images.
5. EXIF stripping — re-encode via Pillow, discarding metadata that can leak the
   photographer's GPS location / device (privacy).

Returns cleaned bytes + the authoritative content type.
"""

from __future__ import annotations

import io

from PIL import Image

from app.config import settings


class UnsafeUpload(Exception):
    """Raised when a file fails validation. `.reason` is user-safe."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


# (magic-byte prefix, content type). WEBP needs the RIFF...WEBP check below.
_MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]

_PIL_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def _sniff(data: bytes) -> str | None:
    for prefix, ctype in _MAGIC:
        if data.startswith(prefix):
            return ctype
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_and_clean(data: bytes) -> tuple[bytes, str]:
    if not data:
        raise UnsafeUpload("Empty file.")
    if len(data) > settings.max_upload_bytes:
        raise UnsafeUpload("File exceeds the maximum allowed size.")

    content_type = _sniff(data)
    if content_type is None or content_type not in settings.allowed_image_types:
        raise UnsafeUpload(
            "Unsupported file type. Allowed: "
            + ", ".join(settings.allowed_image_types)
        )

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()  # detects truncated/corrupt files
        image = Image.open(io.BytesIO(data))  # reopen; verify() exhausts the file
    except Exception:
        raise UnsafeUpload("File is not a valid image.") from None

    limit = settings.max_image_dimension
    if image.width > limit or image.height > limit:
        raise UnsafeUpload(f"Image dimensions exceed {limit}px.")

    # Re-encode WITHOUT the EXIF/info block to strip metadata.
    out = io.BytesIO()
    fmt = _PIL_FORMAT[content_type]
    clean = image.convert("RGB") if fmt == "JPEG" else image
    clean.save(out, format=fmt)
    return out.getvalue(), content_type
