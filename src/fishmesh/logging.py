from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED_RECORD_KEYS = frozenset(
    logging.makeLogRecord({}).__dict__.keys() | {"asctime", "message"}
)


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_RECORD_KEYS and not key.startswith("_")
    }


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat()
        fields = _extras(record)
        suffix = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        line = f"{timestamp} {record.levelname} {record.name} {record.getMessage()}"
        if suffix:
            line = f"{line} {suffix}"
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        return line


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = _extras(record)
        payload.update(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _FishMeshHandler(logging.StreamHandler):
    """Marker class used to update our root handler without duplicating it."""


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure FishMesh's process-wide console logging idempotently."""
    normalized_level = level.upper()
    numeric_level = logging.getLevelNamesMapping().get(normalized_level)
    if numeric_level is None:
        raise ValueError(f"unsupported log level: {level}")

    root = logging.getLogger()
    handlers = [handler for handler in root.handlers if isinstance(handler, _FishMeshHandler)]
    if handlers:
        handler = handlers[0]
        handler.setStream(sys.stderr)
        for duplicate in handlers[1:]:
            root.removeHandler(duplicate)
            duplicate.close()
    else:
        handler = _FishMeshHandler(sys.stderr)
        root.addHandler(handler)

    handler.setLevel(numeric_level)
    handler.setFormatter(_JsonFormatter() if json_output else _TextFormatter())
    root.setLevel(numeric_level)
