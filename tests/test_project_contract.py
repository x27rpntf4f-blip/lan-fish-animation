import tomllib
from pathlib import Path


def test_project_declares_supported_python_and_dependencies() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert any(item.startswith("pygame>=2.5") for item in data["project"]["dependencies"])
