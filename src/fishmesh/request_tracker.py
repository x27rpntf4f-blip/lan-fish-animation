"""Retry deadlines for sprite synchronization requests."""

import time
from collections.abc import Callable


class RequestTracker:
    """Track when incomplete named resources may be requested again."""

    def __init__(
        self,
        retry_after: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._retry_after = retry_after
        self._clock = clock
        self._deadlines: dict[str, float] = {}

    def should_request(self, name: str) -> bool:
        deadline = self._deadlines.get(name)
        return deadline is None or self._clock() >= deadline

    def mark_requested(self, name: str) -> None:
        self._deadlines[name] = self._clock() + self._retry_after

    def mark_complete(self, name: str) -> None:
        self._deadlines.pop(name, None)

    def clear(self) -> None:
        self._deadlines.clear()
