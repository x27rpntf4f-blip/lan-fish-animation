# FishMesh M0-M1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a measurable legacy baseline, fix the highest-risk current defects, and turn the repository into a tested, typed, cross-platform Python project without changing the visible Fish Demo behavior.

**Architecture:** Keep the current UDP protocol and pygame application operational while introducing explicit package boundaries. `fish_demo` owns the application lifecycle and rendering integration; compatibility modules remain available during migration. Pure protocol, configuration, request-tracking, and validation logic are isolated so they can be tested without opening a window and later replaced by `fishmesh-core` V2.

**Tech Stack:** Python 3.11-3.13, pygame 2.5+, asyncio-ready Python packages, uv, pytest, pytest-cov, Ruff, ty, GitHub Actions.

## Global Constraints

- Support Windows, macOS, and Linux.
- Preserve the current Fish Demo features and existing `python src/main.py` entry point during M1.
- Do not add Raft, NAT traversal, a dashboard, or protocol V2 in this plan.
- Do not retain personal absolute paths in tracked configuration.
- Network parsers must reject malformed input without terminating the application loop.
- Use stable, deterministic tests; GUI smoke tests use SDL dummy drivers.
- New or changed behavior is implemented test-first.
- Commit only files belonging to the current task; preserve unrelated worktree changes.
- M1 sprite retry guarantees retry until at least one complete frame is stored; full multi-frame manifests and missing-frame recovery belong to M2 protocol V2.
- M1 quality gates cover new runtime packages, tests, and scripts; report generators and extracted legacy backups remain outside the lint/type-check scope.

---

## Planned File Structure

```text
.
├── .github/workflows/ci.yml           # Three-OS automated quality gate
├── .python-version                    # Local default interpreter version
├── config.example.ini                 # Portable tracked configuration
├── docs/baseline/legacy-m0.md         # Measured legacy behavior and limitations
├── pyproject.toml                     # Build, dependencies, tools, entry points
├── README.md                          # Cross-platform developer and demo guide
├── scripts/capture_legacy_baseline.py # Reproducible M0 evidence capture
├── src/main.py                        # Compatibility entry point only
├── src/fish_demo/
│   ├── __init__.py
│   ├── __main__.py                    # `python -m fish_demo`
│   ├── app.py                         # pygame lifecycle and main loop
│   ├── cli.py                         # Non-interactive CLI parsing
│   ├── input_handlers.py              # Keyboard/fullscreen actions
│   └── network_handlers.py            # V1 message dispatch and sprite send worker
├── src/fishmesh/
│   ├── __init__.py
│   ├── errors.py                      # Typed decode and validation errors
│   ├── sprite_names.py                # Safe resource-name validation
│   └── request_tracker.py             # Retriable missing-resource requests
└── tests/
    ├── conftest.py
    ├── legacy/test_message_v1.py
    ├── legacy/test_runtime_smoke.py
    ├── test_cli.py
    ├── test_message_validation.py
    ├── test_request_tracker.py
    └── test_sprite_names.py
```

## Task 1: Establish the Python Project and Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `tests/conftest.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Existing flat modules under `src/`.
- Produces: `uv sync --extra dev`, `uv run pytest`, `uv run ruff check .`, and `uv run ty check` as repository-wide commands.

- [ ] **Step 1: Write the repository contract test**

Create `tests/conftest.py`:

```python
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
```

Create `tests/test_project_contract.py`:

```python
from pathlib import Path
import tomllib


def test_project_declares_supported_python_and_dependencies() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert any(item.startswith("pygame>=2.5") for item in data["project"]["dependencies"])
```

- [ ] **Step 2: Run the test to verify the missing project metadata fails**

Run: `python3 -m pytest tests/test_project_contract.py -v`

Expected: FAIL because `pyproject.toml` does not exist, or because pytest is not installed in the selected interpreter.

- [ ] **Step 3: Create exact project metadata**

Create `pyproject.toml` with a setuptools `src` layout, project name `fishmesh`, Python floor `>=3.11`, runtime dependency `pygame>=2.5,<3`, optional `video` dependencies `opencv-python>=4.8,<5` and `numpy>=1.26,<3`, and `dev` dependencies `pytest>=8,<9`, `pytest-cov>=5,<7`, `ruff>=0.9,<1`, and `ty>=0.0.1a20`. Define:

```toml
[project.scripts]
fishmesh-demo = "fish_demo.app:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra --strict-markers"

[tool.ruff]
target-version = "py311"
line-length = 100
exclude = ["_zip_extract", "node_modules", "generate_*.py", "build_cheatsheet_pdf.py"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

Set `.python-version` to `3.12`. Extend `.gitignore` with `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, and `.superpowers/` while retaining current entries.

- [ ] **Step 4: Install and verify the toolchain**

Run: `uv sync --extra dev`

Expected: A local environment is created with pygame and the development tools.

Run: `uv run pytest tests/test_project_contract.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .python-version .gitignore tests/conftest.py tests/test_project_contract.py
git commit -m "build: establish FishMesh Python toolchain"
```

## Task 2: Capture the M0 Legacy Baseline

**Files:**
- Create: `tests/legacy/test_message_v1.py`
- Create: `scripts/capture_legacy_baseline.py`
- Create: `docs/baseline/legacy-m0.md`

**Interfaces:**
- Consumes: `message.pack_full`, `message.unpack_full`, all nine V1 message constants, and current source files.
- Produces: `python scripts/capture_legacy_baseline.py --output <path>` and a checked-in baseline document describing measured facts.

- [ ] **Step 1: Write V1 protocol characterization tests**

Create tests that assert the current eight-byte header and representative round trips:

```python
import message


def test_v1_header_is_eight_bytes() -> None:
    assert message.HEADER_SIZE == 8


def test_v1_hello_round_trip() -> None:
    packet = message.pack_hello(2, "node-a", "192.168.1.10", 6000)
    header, payload = message.unpack_full(packet)
    assert header[0] == message.MSG_HELLO
    assert header[1] == 2
    assert message.unpack_hello(payload) == {
        "hostname": "node-a",
        "ip": "192.168.1.10",
        "port": 6000,
    }


def test_v1_heartbeat_carries_sprite_types() -> None:
    packet = message.pack_heartbeat(1, sprite_types=["Fish A", "JinYu"])
    _, payload = message.unpack_full(packet)
    assert message.unpack_heartbeat(payload)["types"] == ["Fish A", "JinYu"]
```

Add round trips for topology, transfer, goodbye, sprite ping, sprite request, and sprite chunk. Use a small local dummy object for the transfer fields; do not initialize pygame.

- [ ] **Step 2: Run the characterization tests**

Run: `uv run pytest tests/legacy/test_message_v1.py -v`

Expected: PASS. These tests freeze current behavior before defensive changes.

- [ ] **Step 3: Implement reproducible baseline capture**

Create a script that reads the repository without changing runtime configuration and writes JSON containing:

```python
{
    "schema_version": 1,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "source_lines": {path: line_count for path in sorted(source_files)},
    "message_header_bytes": message.HEADER_SIZE,
    "message_type_count": len(message.MSG_NAMES),
    "sprite_type_count": len(sprite_directories),
    "tracked_personal_paths": personal_path_matches,
}
```

CLI signature:

```python
def main(argv: list[str] | None = None) -> int:
    ...
```

Arguments: `--output PATH`, defaulting to `artifacts/baseline/legacy-m0.json`. Create the output parent directory and serialize UTF-8 JSON with sorted keys and indentation.

- [ ] **Step 4: Capture and document the baseline**

Run: `uv run python scripts/capture_legacy_baseline.py --output /tmp/fishmesh-legacy-m0.json`

Expected: JSON exists and reports nine message types and the current personal path in `config.ini`.

Create `docs/baseline/legacy-m0.md` containing the command, environment, current module inventory, confirmed defects, and a table with columns `Capability`, `Current behavior`, `Evidence`, and `M1 action`. Include malformed-packet crashes, sprite request retry suppression, mutable host IDs, direct main-thread sends, and the personal background path.

- [ ] **Step 5: Commit**

```bash
git add tests/legacy/test_message_v1.py scripts/capture_legacy_baseline.py docs/baseline/legacy-m0.md
git commit -m "test: capture legacy FishMesh baseline"
```

## Task 3: Make V1 Packet Decoding Fail Closed

**Files:**
- Create: `src/fishmesh/__init__.py`
- Create: `src/fishmesh/errors.py`
- Modify: `src/message.py:37-48`
- Modify: `src/main.py:152-157`
- Create: `tests/test_message_validation.py`

**Interfaces:**
- Consumes: Raw UDP datagrams as `bytes`.
- Produces: `message.unpack_full(data: bytes) -> tuple[tuple[int, int, int, int], bytes]`; raises `PacketDecodeError` for invalid data.

- [ ] **Step 1: Write malformed-packet tests**

```python
import pytest

import message
from fishmesh.errors import PacketDecodeError


@pytest.mark.parametrize("packet", [b"", b"\x01", b"\x01\x02\x03\x04\x05\x06\x07"])
def test_unpack_full_rejects_short_header(packet: bytes) -> None:
    with pytest.raises(PacketDecodeError, match="header"):
        message.unpack_full(packet)


def test_unpack_full_rejects_truncated_payload() -> None:
    packet = message.pack_header(message.MSG_HELLO, 0, b"12345") + b"12"
    with pytest.raises(PacketDecodeError, match="payload"):
        message.unpack_full(packet)


def test_unpack_full_rejects_unknown_message_type() -> None:
    packet = message.pack_full(0xFE, 0, b"")
    with pytest.raises(PacketDecodeError, match="message type"):
        message.unpack_full(packet)
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/test_message_validation.py -v`

Expected: FAIL because `PacketDecodeError` and validation do not exist.

- [ ] **Step 3: Implement typed validation**

Define:

```python
class FishMeshError(Exception):
    """Base class for recoverable FishMesh errors."""


class PacketDecodeError(FishMeshError, ValueError):
    """A datagram is malformed or unsupported and must be discarded."""
```

Update `unpack_full` to check header length, catch `struct.error`, reject unknown types, require exact declared payload availability, and return only the declared payload. Update the main message handler to catch `PacketDecodeError`, log and discard the packet without mutating registry or fish state.

- [ ] **Step 4: Verify validation and legacy compatibility**

Run: `uv run pytest tests/test_message_validation.py tests/legacy/test_message_v1.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fishmesh/__init__.py src/fishmesh/errors.py src/message.py src/main.py tests/test_message_validation.py
git commit -m "fix: reject malformed V1 datagrams safely"
```

## Task 4: Restore Retriable Sprite Synchronization

**Files:**
- Create: `src/fishmesh/request_tracker.py`
- Modify: `src/main.py:183-214`
- Modify: `src/main.py:265-279`
- Modify: `src/main.py:281-289`
- Create: `tests/test_request_tracker.py`

**Interfaces:**
- Produces: `RequestTracker(retry_after: float, clock: Callable[[], float])` with `should_request(name: str) -> bool`, `mark_requested(name: str) -> None`, `mark_complete(name: str) -> None`, and `clear() -> None`.
- Consumers: Heartbeat and sprite-ping handlers.

- [ ] **Step 1: Write tracker behavior tests**

```python
from fishmesh.request_tracker import RequestTracker


def test_request_is_retried_after_deadline() -> None:
    now = [100.0]
    tracker = RequestTracker(retry_after=3.0, clock=lambda: now[0])
    assert tracker.should_request("Purple")
    tracker.mark_requested("Purple")
    assert not tracker.should_request("Purple")
    now[0] = 103.0
    assert tracker.should_request("Purple")


def test_completion_removes_pending_request() -> None:
    tracker = RequestTracker(retry_after=3.0)
    tracker.mark_requested("Purple")
    tracker.mark_complete("Purple")
    assert tracker.should_request("Purple")
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/test_request_tracker.py -v`

Expected: FAIL because the tracker does not exist.

- [ ] **Step 3: Implement the minimal tracker and integrate it**

Store `dict[str, float]` deadlines. Replace dynamic `reg._pending_requests` sets with one tracker created during app startup and passed to `handle_network_message`. When at least one complete sprite frame becomes locally available, call `mark_complete(info["name"])`. Both heartbeat and sprite-ping request paths call `should_request` and `mark_requested`. Record the V1 limitation explicitly: because the packet format has no total-frame manifest, M1 cannot detect a missing later frame after the type directory becomes visible; M2 protocol V2 owns full multi-frame completeness and missing-frame recovery.

- [ ] **Step 4: Verify retry behavior and protocol compatibility**

Run: `uv run pytest tests/test_request_tracker.py tests/legacy/test_message_v1.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fishmesh/request_tracker.py src/main.py tests/test_request_tracker.py
git commit -m "fix: retry interrupted sprite synchronization"
```

## Task 5: Prevent Sprite Path Escape and Invalid Resource Writes

**Files:**
- Create: `src/fishmesh/sprite_names.py`
- Modify: `src/sprite_sync.py:53-123`
- Modify: `src/sprite_manager.py:157-218`
- Modify: `src/main.py:112-133`
- Create: `tests/test_sprite_names.py`

**Interfaces:**
- Produces: `validate_sprite_name(value: str) -> str`, raising `InvalidSpriteName`.
- Consumers: Local import, sprite request sender, and network chunk receiver.

- [ ] **Step 1: Write validation tests**

```python
import pytest

from fishmesh.sprite_names import InvalidSpriteName, validate_sprite_name


@pytest.mark.parametrize("value", ["Fish A", "JinYu", "purple-2", "锦鲤"])
def test_valid_sprite_names_are_preserved(value: str) -> None:
    assert validate_sprite_name(value) == value


@pytest.mark.parametrize("value", ["", ".", "..", "../escape", "a/b", "a\\b", "\x00bad"])
def test_unsafe_sprite_names_are_rejected(value: str) -> None:
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name(value)
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/test_sprite_names.py -v`

Expected: FAIL because validation does not exist.

- [ ] **Step 3: Implement canonical name validation**

Normalize Unicode with NFC, trim surrounding whitespace, allow 1-64 characters, reject control characters, path separators, `.` and `..`. Resolve the destination path and assert it remains a direct child of the configured sprite root before creating directories or writing files. Reject invalid remote chunks without saving partial data.

- [ ] **Step 4: Verify validation and an end-to-end safe write**

Add a test using `tmp_path` that feeds one valid complete chunk to `SpriteSyncManager` and asserts the resulting file is `tmp_path / "Purple" / "Fish-1.png"`. Assert that `../escape` raises `InvalidSpriteName` and produces no file outside `tmp_path`.

Run: `uv run pytest tests/test_sprite_names.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fishmesh/sprite_names.py src/sprite_sync.py src/sprite_manager.py src/main.py tests/test_sprite_names.py
git commit -m "fix: validate sprite resource paths"
```

## Task 6: Add Non-Interactive CLI and Headless Runtime Smoke Test

**Files:**
- Create: `src/fish_demo/__init__.py`
- Create: `src/fish_demo/cli.py`
- Modify: `src/main.py:71-75`
- Modify: `src/main.py:310-338`
- Modify: `src/main.py:424-645`
- Create: `tests/test_cli.py`
- Create: `tests/legacy/test_runtime_smoke.py`

**Interfaces:**
- Produces: `parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace` with `--port`, `--expected-hosts`, `--run-seconds`, `--windowed`, and `--no-audio`.
- Consumers: Legacy `main()` and CI smoke test.

- [ ] **Step 1: Write CLI tests**

```python
from fish_demo.cli import parse_args


def test_non_interactive_arguments() -> None:
    args = parse_args([
        "--port", "6200",
        "--expected-hosts", "3",
        "--run-seconds", "0.2",
        "--windowed",
        "--no-audio",
    ])
    assert args.port == 6200
    assert args.expected_hosts == 3
    assert args.run_seconds == 0.2
    assert args.windowed
    assert args.no_audio
```

- [ ] **Step 2: Verify the CLI test fails**

Run: `uv run pytest tests/test_cli.py -v`

Expected: FAIL because `fish_demo.cli` does not exist.

- [ ] **Step 3: Implement CLI parsing and runtime overrides**

Validate `expected_hosts` in `[1, 10]`, port in `[1, 65535]`, and non-negative run duration. When `--expected-hosts` is supplied, skip `input()`. `--run-seconds` exits the loop after monotonic elapsed time. `--windowed` and `--no-audio` override loaded configuration in memory but do not persist those diagnostic overrides.

- [ ] **Step 4: Write and run a subprocess smoke test**

```python
import os
import subprocess
import sys


def test_legacy_app_starts_and_stops_headlessly() -> None:
    env = os.environ | {
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "PYTHONPATH": "src",
    }
    result = subprocess.run(
        [
            sys.executable,
            "src/main.py",
            "--expected-hosts", "1",
            "--run-seconds", "0.2",
            "--windowed",
            "--no-audio",
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
```

Run: `uv run pytest tests/test_cli.py tests/legacy/test_runtime_smoke.py -v`

Expected: PASS without opening a visible window or waiting for terminal input.

- [ ] **Step 5: Commit**

```bash
git add src/fish_demo/__init__.py src/fish_demo/cli.py src/main.py tests/test_cli.py tests/legacy/test_runtime_smoke.py
git commit -m "feat: add deterministic headless demo mode"
```

## Task 7: Split the Main Module at Stable Seams

**Files:**
- Create: `src/fish_demo/input_handlers.py`
- Create: `src/fish_demo/network_handlers.py`
- Create: `src/fish_demo/app.py`
- Create: `src/fish_demo/__main__.py`
- Modify: `src/main.py`
- Modify: `tests/legacy/test_runtime_smoke.py`

**Interfaces:**
- Produces: `fish_demo.app.main(argv: Sequence[str] | None = None) -> int`.
- Produces: `handle_key(...)`, `handle_network_message(...)`, and `send_sprite_data_async(...)` in focused modules with their existing externally observable behavior.
- Keeps: `src/main.py` as a compatibility shim importing and invoking `fish_demo.app.main`.

- [ ] **Step 1: Add entry-point equivalence tests**

Parameterize the headless smoke test over:

```python
commands = [
    [sys.executable, "src/main.py"],
    [sys.executable, "-m", "fish_demo"],
]
```

Append the same diagnostic arguments to each command and require both to exit zero.

- [ ] **Step 2: Run the test before package entry points exist**

Run: `uv run pytest tests/legacy/test_runtime_smoke.py -v`

Expected: FAIL for `python -m fish_demo`.

- [ ] **Step 3: Move code without changing behavior**

Move keyboard/fullscreen helpers to `input_handlers.py`, network message dispatch and sprite sending to `network_handlers.py`, and the lifecycle/main loop to `app.py`. Use explicit imports rather than wildcard imports. Define:

```python
# src/main.py
from fish_demo.app import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Define `src/fish_demo/__main__.py` with the same call. Return `0` on clean shutdown from `app.main`.

- [ ] **Step 4: Run behavior and import checks**

Run: `uv run pytest tests/legacy/test_runtime_smoke.py tests/legacy/test_message_v1.py -v`

Expected: PASS for both entry points and all frozen protocol behavior.

Run: `uv run python -m compileall -q src`

Expected: Exit 0.

- [ ] **Step 5: Commit**

```bash
git add src/main.py src/fish_demo tests/legacy/test_runtime_smoke.py
git commit -m "refactor: split Fish Demo application lifecycle"
```

## Task 8: Make Configuration Portable and Explicit

**Files:**
- Create: `config.example.ini`
- Modify: `config.ini`
- Modify: `src/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `load(path: Path | None = None) -> ConfigParser` and `save(cfg: ConfigParser, path: Path | None = None) -> None` using UTF-8.
- Consumers: `fish_demo.app` and tests.

- [ ] **Step 1: Write portability tests**

```python
from pathlib import Path

from config import load, save


def test_load_uses_portable_defaults_when_file_is_missing(tmp_path: Path) -> None:
    cfg = load(tmp_path / "missing.ini")
    assert cfg["Background"]["type"] == "gradient"
    assert cfg["Background"]["path"] == ""


def test_save_round_trips_unicode_as_utf8(tmp_path: Path) -> None:
    path = tmp_path / "config.ini"
    cfg = load(path)
    cfg["Background"]["path"] = "素材/海底.png"
    save(cfg, path)
    assert load(path)["Background"]["path"] == "素材/海底.png"
```

- [ ] **Step 2: Verify the tests fail**

Run: `uv run pytest tests/test_config.py -v`

Expected: FAIL because `load` and `save` do not accept a path and do not explicitly use UTF-8.

- [ ] **Step 3: Implement path injection and clean tracked defaults**

Use `pathlib.Path`, `encoding="utf-8"`, and an optional path parameter. Change tracked `config.ini` to windowed `800x600`, five fish, speed `1.0`, expected hosts `2`, enabled audio, and gradient background with an empty path. Copy the same portable values to `config.example.ini`.

- [ ] **Step 4: Run configuration and headless tests**

Run: `uv run pytest tests/test_config.py tests/legacy/test_runtime_smoke.py -v`

Expected: PASS; the smoke test must not rewrite tracked configuration.

- [ ] **Step 5: Commit**

```bash
git add config.ini config.example.ini src/config.py tests/test_config.py
git commit -m "fix: make runtime configuration portable"
```

## Task 9: Add Structured Logging at Runtime Boundaries

**Files:**
- Create: `src/fishmesh/logging.py`
- Modify: `src/network.py`
- Modify: `src/sprite_manager.py`
- Modify: `src/sprite_sync.py`
- Modify: `src/fish_demo/app.py`
- Create: `tests/test_logging.py`

**Interfaces:**
- Produces: `configure_logging(level: str = "INFO", json_output: bool = False) -> None` and module loggers obtained with `logging.getLogger(__name__)`.
- Consumers: Runtime and future M2 metrics integration.

- [ ] **Step 1: Write logging tests**

Use `caplog` to assert a malformed packet produces a warning with event name `packet_discarded`, and a completed sprite frame produces `sprite_frame_saved` with the sprite name and frame index. Assert expected information is in `LogRecord` extras, not only formatted prose.

- [ ] **Step 2: Verify logging tests fail**

Run: `uv run pytest tests/test_logging.py -v`

Expected: FAIL because runtime modules still print or silently suppress errors.

- [ ] **Step 3: Introduce logging without changing recovery semantics**

Replace diagnostic `print` calls and silent network `OSError` handling with appropriately leveled log events. Do not log every heartbeat at INFO. Keep rendering independent of logging. Add `--log-level` to the CLI with choices `DEBUG`, `INFO`, `WARNING`, and `ERROR`.

- [ ] **Step 4: Run logging and smoke tests**

Run: `uv run pytest tests/test_logging.py tests/legacy/test_runtime_smoke.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fishmesh/logging.py src/network.py src/sprite_manager.py src/sprite_sync.py src/fish_demo/app.py src/fish_demo/cli.py tests/test_logging.py
git commit -m "feat: add structured runtime logging"
```

## Task 10: Add Three-Platform CI and Contributor Documentation

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `README.md`
- Modify: `docs/baseline/legacy-m0.md`

**Interfaces:**
- Consumes: Repository commands established in Task 1.
- Produces: Repeatable local and CI validation on Ubuntu, macOS, and Windows.

- [ ] **Step 1: Create a documentation contract test**

Create `tests/test_documentation.py`:

```python
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
```

- [ ] **Step 2: Verify the documentation test fails**

Run: `uv run pytest tests/test_documentation.py -v`

Expected: FAIL because `README.md` does not exist.

- [ ] **Step 3: Write README and CI workflow**

README sections: project positioning, current M1 scope, architecture boundary, prerequisites, development setup, ordinary demo launch, headless smoke launch, test/quality commands, three-machine LAN setup, known limitations, and roadmap link.

CI matrix:

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python: ["3.11", "3.12", "3.13"]
```

Install uv using `astral-sh/setup-uv@v6`, install the requested matrix Python, run `uv sync --extra dev`, then Ruff over `src/fishmesh src/fish_demo tests scripts`, ty over `src/fishmesh src/fish_demo`, pytest with coverage, and the headless runtime smoke test. Set SDL dummy drivers for the test steps.

- [ ] **Step 4: Run the complete local M0-M1 quality gate**

Run:

```bash
uv run ruff check src/fishmesh src/fish_demo tests scripts
uv run ty check src/fishmesh src/fish_demo
uv run pytest --cov=src --cov-report=term-missing
uv run python -m compileall -q src
git diff --check
```

Expected: All commands exit 0. Core pure-Python modules meet the coverage target; pygame-heavy legacy presentation modules may be explicitly omitted from the initial coverage denominator and documented.

- [ ] **Step 5: Update the baseline with measured M1 comparison**

Append an `M1 Result` section to `docs/baseline/legacy-m0.md` with the actual test count, coverage, supported interpreter matrix, resolved defects, remaining limitations, and exact local environment. Do not enter estimated numbers.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml README.md tests/test_documentation.py docs/baseline/legacy-m0.md
git commit -m "ci: validate FishMesh foundation across platforms"
```

## Task 11: M0-M1 Release Verification

**Files:**
- Modify only if verification exposes a defect: files owned by Tasks 1-10.
- Create: `docs/releases/m1-foundation.md`

**Interfaces:**
- Consumes: All M0-M1 commands and artifacts.
- Produces: A release-quality verification record and tag candidate `m1-foundation`.

- [ ] **Step 1: Run the complete quality gate from a clean process**

Run the five commands from Task 10 Step 4, then run both entry points with `--expected-hosts 1 --run-seconds 1 --windowed --no-audio`.

Expected: All commands exit 0, no visible window opens with dummy SDL, and tracked configuration remains unchanged.

- [ ] **Step 2: Inspect repository scope**

Run:

```bash
git status --short
git diff --stat "$(git merge-base main HEAD)"..HEAD
git log --oneline --decorate -12
```

Expected: The isolated worktree is clean and M0-M1 commits contain only planned files. The controller separately verifies that pre-existing changes in the original checkout remain untouched.

- [ ] **Step 3: Write the release record**

Document the exact environment, commands, pass/fail results, known limitations, and next plan boundary. State that protocol V2, SWIM-inspired membership, two-dimensional topology, simulator, and dashboard are intentionally deferred to subsequent plans.

- [ ] **Step 4: Commit**

```bash
git add docs/releases/m1-foundation.md
git commit -m "docs: record M1 foundation verification"
```

## Subsequent Independent Plans

After M0-M1 passes its release gate, create and approve these plans in order:

1. **M2 Protocol V2:** versioned envelope, UUID/session identity, ACK/retry/dedup, reliable resource transfer, bounded queues, compatibility adapter.
2. **M3 Cluster Runtime:** SWIM-inspired membership, two-dimensional layout, migration ownership state machine, rollback and convergence tests.
3. **M4 Experiment Platform:** multi-process orchestration, deterministic fault injection, metrics model, monitoring dashboard, JSON/CSV reports.
4. **M5 Portfolio Release:** installers, real three-device lab protocol, demonstration video, public documentation and release packaging.
5. **M6+ Research Extensions:** one separately approved experimental question per plan.
