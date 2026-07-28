from __future__ import annotations

import pytest

from fish_demo.cli import parse_args


def test_non_interactive_arguments_are_parsed() -> None:
    """Would fail if the diagnostic CLI cannot configure a finite run."""
    args = parse_args(
        [
            "--port",
            "6200",
            "--expected-hosts",
            "3",
            "--run-seconds",
            "0.2",
            "--windowed",
            "--no-audio",
        ]
    )

    assert args.port == 6200
    assert args.expected_hosts == 3
    assert args.run_seconds == 0.2
    assert args.windowed is True
    assert args.no_audio is True


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--port", "0"], "port"),
        (["--port", "65536"], "port"),
        (["--expected-hosts", "0"], "expected-hosts"),
        (["--expected-hosts", "11"], "expected-hosts"),
        (["--run-seconds", "-0.1"], "run-seconds"),
        (["--run-seconds", "nan"], "run-seconds"),
    ],
)
def test_invalid_diagnostic_values_are_rejected(argv: list[str], message: str) -> None:
    """Would fail if out-of-range CLI input reaches the runtime."""
    with pytest.raises(SystemExit, match="2"):
        parse_args(argv)
