import subprocess
import tomllib
from pathlib import Path


def test_project_declares_supported_python_and_dependencies() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert any(item.startswith("pygame>=2.5") for item in data["project"]["dependencies"])


def test_repository_does_not_track_python_bytecode() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )

    tracked_bytecode = [
        path
        for path in result.stdout.splitlines()
        if "__pycache__" in Path(path).parts or path.endswith(".pyc")
    ]

    assert tracked_bytecode == []
