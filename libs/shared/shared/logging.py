"""Structured JSON logging shared by every service.

Emitting one JSON object per line makes logs greppable and lets a log
aggregator (Loki, CloudWatch, ELK) parse fields without regexes — the
observability baseline referenced in the deployment notes.
"""

from __future__ import annotations

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", *, service: str | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    if service:
        logging.getLogger(service).info("logging configured")
