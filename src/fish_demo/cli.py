"""Non-interactive command-line options for the FishMesh demo."""

from __future__ import annotations

import argparse
import math
from collections.abc import Sequence


def _bounded_int(name: str, minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(f"{name} must be between {minimum} and {maximum}")
        return parsed

    return parse


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("run-seconds must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("run-seconds must be a finite non-negative number")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse interactive and deterministic diagnostic runtime options."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=_bounded_int("port", 1, 65535),
        default=None,
        help="UDP port (default: configured port)",
    )
    parser.add_argument(
        "--expected-hosts",
        type=_bounded_int("expected-hosts", 1, 10),
        default=None,
        help="mesh host count; skips the interactive prompt",
    )
    parser.add_argument(
        "--run-seconds",
        type=_non_negative_float,
        default=None,
        help="exit after this many monotonic seconds",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="run windowed without persisting the display override",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="disable audio without persisting the audio override",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="minimum runtime log level (default: INFO)",
    )
    return parser.parse_args(argv)
