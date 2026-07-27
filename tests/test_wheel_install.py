from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pygame

RUNTIME_MODULES = (
    "audio_manager",
    "background_manager",
    "config",
    "fish_entity",
    "main",
    "message",
    "network",
    "renderer",
    "sprite_manager",
    "sprite_sync",
    "ui",
)


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def test_wheel_console_loads_all_runtime_modules_without_editable_source(tmp_path: Path) -> None:
    """Would fail when the wheel omits any module imported by the demo application."""
    source_root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    assert uv is not None

    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}
    }
    clean_env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "SDL_AUDIODRIVER": "dummy",
            "SDL_VIDEODRIVER": "dummy",
        }
    )

    project_root = tmp_path / "source"
    project_root.mkdir()
    shutil.copy2(source_root / "pyproject.toml", project_root / "pyproject.toml")
    shutil.copytree(source_root / "src", project_root / "src")

    dist_dir = tmp_path / "dist"
    build = _run(
        [uv, "build", "--wheel", "--offline", "--out-dir", str(dist_dir)],
        cwd=project_root,
        env=clean_env,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(dist_dir.glob("fishmesh-*.whl"))

    environment = tmp_path / "wheel-env"
    create = _run(
        [uv, "venv", "--offline", "--python", sys.executable, str(environment)],
        cwd=tmp_path,
        env=clean_env,
    )
    assert create.returncode == 0, create.stderr

    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = _run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--python",
            str(python),
            str(wheel),
        ],
        cwd=tmp_path,
        env=clean_env,
    )
    assert install.returncode == 0, install.stderr

    site_packages_result = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        cwd=tmp_path,
        env=clean_env,
    )
    assert site_packages_result.returncode == 0, site_packages_result.stderr
    site_packages = Path(site_packages_result.stdout.strip())
    shutil.copytree(Path(pygame.__file__).parent, site_packages / "pygame")

    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    console = scripts / ("fishmesh-demo.exe" if os.name == "nt" else "fishmesh-demo")
    help_result = _run([str(console), "--help"], cwd=tmp_path, env=clean_env)
    assert help_result.returncode == 0, help_result.stderr
    assert "--expected-hosts" in help_result.stdout

    imports = ", ".join(("fish_demo.app", "fishmesh.request_tracker", *RUNTIME_MODULES))
    import_result = _run(
        [str(python), "-c", f"import {imports}"],
        cwd=tmp_path,
        env=clean_env,
    )
    assert import_result.returncode == 0, import_result.stderr
