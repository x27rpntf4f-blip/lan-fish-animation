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


def test_ci_pins_and_verifies_each_matrix_python() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    for contract in (
        "UV_PYTHON: ${{ matrix.python }}",
        "uv sync --locked --extra dev",
        "EXPECTED_PYTHON: ${{ matrix.python }}",
        "platform.python_version()",
        "actual.startswith(expected + '.')",
    ):
        assert contract in text
