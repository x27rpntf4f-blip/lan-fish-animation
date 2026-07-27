# Task 8: Portable Runtime Configuration

## Result

- `load()` and `save()` accept an optional `pathlib.Path` and explicitly use UTF-8.
- With no path supplied, the runtime uses `Path.cwd() / "config.ini"`. This makes the
  ordinary repository launch use the tracked file while a wheel installation writes to
  its user-selected working directory rather than its read-only site-packages directory.
- Missing configuration files receive the complete portable defaults. Saves create their
  parent directory when necessary.
- `config.ini` and `config.example.ini` are byte-for-byte identical portable templates:
  windowed 800x600, five fish, speed 1.0, two expected hosts, audio enabled, and an
  empty gradient background path.

## Test evidence

- RED: `uv run pytest tests/test_config.py -v` failed 4/4 on the previous API.
- GREEN: `uv run pytest tests/test_config.py -v` passed 4/4.
- `uv run pytest tests/test_config.py tests/legacy/test_runtime_smoke.py -v` passed 6/6.
- `uv run pytest tests/test_wheel_install.py -v` passed 1/1.
- `uv run pytest -q` passed 122/122; the configuration SHA-256 was identical before
  and after this final run.
- `uv run ruff check src/fishmesh src/fish_demo tests scripts` passed.
- `uv run ty check src/fishmesh src/fish_demo` passed.

The legacy baseline capture assertion was updated to verify that tracked personal paths
are absent, matching the portable configuration requirement.
