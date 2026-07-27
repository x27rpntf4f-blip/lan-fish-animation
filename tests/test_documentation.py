from pathlib import Path


def test_readme_contains_required_workflows() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    for command in (
        "uv sync --extra dev",
        "uv run fishmesh-demo",
        "uv run pytest",
        "uv run ruff check src/fishmesh src/fish_demo tests scripts",
        "uv run ty check src/fishmesh src/fish_demo",
    ):
        assert command in text
