from __future__ import annotations

import hashlib
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


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
    return digest.hexdigest()


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
            "FISHMESH_DATA_DIR": str(tmp_path / "user-data"),
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
    installed_digest = _tree_digest(site_packages)

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

    no_source_cwd = tmp_path / "empty-cwd"
    no_source_cwd.mkdir()
    runtime = _run(
        [
            str(console),
            "--expected-hosts",
            "1",
            "--run-seconds",
            "0.2",
            "--windowed",
            "--no-audio",
        ],
        cwd=no_source_cwd,
        env=clean_env,
    )

    assert runtime.returncode == 0, runtime.stderr
    assert "sprite_count=10" in runtime.stderr
    assert _tree_digest(site_packages) == installed_digest
