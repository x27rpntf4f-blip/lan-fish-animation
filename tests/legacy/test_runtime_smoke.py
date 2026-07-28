from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def _available_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _asset_entries(project_root: Path) -> set[Path]:
    sprite_root = project_root / "assets" / "fish_sprites"
    return set(sprite_root.rglob("*"))


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, "src/main.py"],
        [sys.executable, "-m", "fish_demo"],
    ],
    ids=["compatibility-script", "package-module"],
)
def test_legacy_app_starts_and_stops_headlessly(command: list[str]) -> None:
    """Would fail if diagnostic mode waits for input or leaks its runtime."""
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config.ini"
    config_before = config_path.read_bytes()
    assets_before = _asset_entries(project_root)
    env = os.environ | {
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "PYTHONPATH": str(project_root / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        result = subprocess.run(
            command
            + [
                "--port",
                str(_available_udp_port()),
                "--expected-hosts",
                "1",
                "--run-seconds",
                "0.2",
                "--windowed",
                "--no-audio",
            ],
            cwd=project_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    finally:
        created_paths = _asset_entries(project_root) - assets_before
        for path in created_paths:
            if path.is_file():
                path.unlink()
        for path in sorted(created_paths, key=lambda path: len(path.parts), reverse=True):
            if path.is_dir():
                path.rmdir()

    assert result.returncode == 0, result.stderr
    assert config_path.read_bytes() == config_before
