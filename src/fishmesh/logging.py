from __future__ import annotations

import json
import logging
import math
import sys
import threading
import time
from collections.abc import Callable, Hashable, Mapping
from datetime import UTC, datetime
from typing import Any

_RESERVED_RECORD_KEYS = frozenset(
    logging.makeLogRecord({}).__dict__.keys() | {"asctime", "message"}
)
_MAX_JSON_DEPTH = 8
_PROJECT_LOGGER_NAMES = (
    "fishmesh",
    "fish_demo",
    "network",
    "audio_manager",
    "sprite_manager",
    "sprite_sync",
)


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_RECORD_KEYS and not key.startswith("_")
    }


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return f"<unprintable {type(value).__name__}>"


def _exception_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {_safe_text(exc)}"


def _normalize_json(
    value: Any,
    *,
    depth: int = 0,
    active_ids: set[int] | None = None,
) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, BaseException):
        return _safe_text(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if depth >= _MAX_JSON_DEPTH:
        return "<max_depth>"

    if active_ids is None:
        active_ids = set()
    value_id = id(value)
    if value_id in active_ids:
        return "<cycle>"

    if isinstance(value, Mapping):
        active_ids.add(value_id)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = key if isinstance(key, str) else _safe_text(key)
                normalized[normalized_key] = _normalize_json(
                    item,
                    depth=depth + 1,
                    active_ids=active_ids,
                )
            return normalized
        except Exception as exc:
            return f"<mapping normalization failed: {_exception_text(exc)}>"
        finally:
            active_ids.remove(value_id)

    if isinstance(value, (list, tuple, set, frozenset)):
        active_ids.add(value_id)
        try:
            items = list(value)
            if isinstance(value, (set, frozenset)):
                items.sort(key=_safe_text)
            return [
                _normalize_json(item, depth=depth + 1, active_ids=active_ids)
                for item in items
            ]
        except Exception as exc:
            return f"<sequence normalization failed: {_exception_text(exc)}>"
        finally:
            active_ids.remove(value_id)

    return _safe_text(value)


class EventRateLimiter:
    """Suppress repeated event/key pairs during a monotonic time window."""

    def __init__(
        self,
        window_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window_seconds = window_seconds
        self._clock = clock
        self._states: dict[tuple[str, Hashable], tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, event: str, stable_key: Hashable) -> int | None:
        """Return suppressed count when emission is allowed, otherwise None."""
        now = self._clock()
        state_key = (event, stable_key)
        with self._lock:
            previous = self._states.get(state_key)
            if previous is None:
                self._states[state_key] = (now, 0)
                return 0

            last_emitted, suppressed_count = previous
            if now - last_emitted < self._window_seconds:
                self._states[state_key] = (last_emitted, suppressed_count + 1)
                return None

            self._states[state_key] = (now, 0)
            return suppressed_count


_NETWORK_EVENT_LIMITER = EventRateLimiter()


def log_rate_limited_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    event: str,
    stable_key: Hashable,
    extra: Mapping[str, Any],
    limiter: EventRateLimiter | None = None,
) -> None:
    if limiter is None:
        limiter = _NETWORK_EVENT_LIMITER
    suppressed_count = limiter.check(event, stable_key)
    if suppressed_count is None:
        return
    fields = dict(extra)
    fields["event"] = event
    if suppressed_count:
        fields["suppressed_count"] = suppressed_count
    logger.log(level, message, extra=fields)


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
        try:
            format_error = None
            try:
                message = record.getMessage()
            except Exception as exc:
                message = "<message formatting failed>"
                format_error = _exception_text(exc)

            payload = _normalize_json(_extras(record))
            payload.update(
                {
                    "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                    "level": _safe_text(record.levelname),
                    "logger": _safe_text(record.name),
                    "message": _normalize_json(message),
                }
            )
            if format_error is not None:
                payload["format_error"] = format_error
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False, allow_nan=False)
        except Exception as exc:
            fallback = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": _safe_text(getattr(record, "levelname", "ERROR")),
                "logger": _safe_text(getattr(record, "name", "fishmesh.logging")),
                "message": "<log formatting failed>",
                "event": _normalize_json(record.__dict__.get("event", "logging_format_failed")),
                "format_error": _exception_text(exc),
            }
            return json.dumps(fallback, ensure_ascii=False, allow_nan=False)


class _FishMeshHandler(logging.StreamHandler):
    """Marker class used to update our root handler without duplicating it."""


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure FishMesh runtime loggers without changing root logging."""
    normalized_level = level.upper()
    numeric_level = logging.getLevelNamesMapping().get(normalized_level)
    if numeric_level is None:
        raise ValueError(f"unsupported log level: {level}")

    project_loggers = [logging.getLogger(name) for name in _PROJECT_LOGGER_NAMES]
    handlers = []
    for project_logger in project_loggers:
        for candidate in project_logger.handlers:
            if isinstance(candidate, _FishMeshHandler) and candidate not in handlers:
                handlers.append(candidate)

    if handlers:
        handler = handlers[0]
        handler.setStream(sys.stderr)
    else:
        handler = _FishMeshHandler(sys.stderr)

    handler.setLevel(numeric_level)
    handler.setFormatter(_JsonFormatter() if json_output else _TextFormatter())
    for project_logger in project_loggers:
        for candidate in project_logger.handlers[:]:
            if isinstance(candidate, _FishMeshHandler) and candidate is not handler:
                project_logger.removeHandler(candidate)
        if handler not in project_logger.handlers:
            project_logger.addHandler(handler)
        project_logger.setLevel(numeric_level)
        project_logger.propagate = False

    for duplicate in handlers[1:]:
        duplicate.close()
