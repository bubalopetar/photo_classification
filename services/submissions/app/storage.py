"""Photo storage layer.

The DB stores only an object key; the bytes live here, on a local directory
(a mounted volume in Docker). `Storage` is the seam a cloud backend plugs into
later — an S3/GCS implementation only needs `put`/`get` and one line in
`get_storage()`; nothing else in the service changes.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from app.config import settings

_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def new_key(content_type: str) -> str:
    """Server-generated object key. Never derived from the client filename, so a
    malicious name can't traverse paths or collide with another object."""
    return f"{uuid.uuid4()}.{_EXT.get(content_type, 'bin')}"


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, directory: str):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        # Re-created per write: the directory can be deleted while the service
        # runs, and that must not turn every upload into a 500.
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / key).write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self._dir / key).read_bytes()

    def delete(self, key: str) -> None:
        (self._dir / key).unlink(missing_ok=True)


def get_storage() -> Storage:
    return LocalStorage(settings.storage_local_dir)


storage: Storage = get_storage()
