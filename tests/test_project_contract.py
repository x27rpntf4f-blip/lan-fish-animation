import subprocess
import tomllib
from pathlib import Path


def test_project_declares_supported_python_and_dependencies() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert any(item.startswith("pygame>=2.5") for item in data["project"]["dependencies"])


def test_repository_does_not_track_python_bytecode(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        cwd=repository_root,
    )

    tracked_bytecode = [
        path
        for path in result.stdout.split(b"\0")
        if path
        if b"__pycache__" in path.split(b"/") or path.endswith(b".pyc")
    ]

    assert tracked_bytecode == []
