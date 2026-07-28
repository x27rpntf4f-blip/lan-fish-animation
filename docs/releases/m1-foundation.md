# FishMesh M1 Foundation Release Verification

## Candidate status

- Verification date: 2026-07-28 (Asia/Shanghai).
- Branch: `codex/fishmesh-m0-m1`.
- Code commit under verification: `34fd60e3135c8904f71595188c27f2fdeb25e867`.
- Final-hardening base: `d4c92f4f95f1811740af0c442e94c3dfee002153`.
- Original project base: `603f7d31c795bac58740765b041c6bacc26f8659` (`main`).
- This release record is a documentation-only descendant of the code commit.
- No Git tag was created. Remote CI and real three-device evidence remain pending.

## Local environment

| Component | Verified value |
| --- | --- |
| Operating system | macOS 26.5.2, build 25F84, arm64 |
| Python | 3.12.13, Clang 17.0.0 (`clang-1700.6.3.2`) |
| uv | 0.11.28 (Homebrew 2026-07-07, aarch64-apple-darwin) |
| pygame / SDL | pygame 2.6.1 / SDL 2.28.4 |
| Ruff | 0.16.0 |
| ty | 0.0.63 (`46f4915e6`, 2026-07-23) |
| pytest / pytest-cov | 8.4.2 / 6.3.0 |

Python verification used `PYTHONDONTWRITEBYTECODE=1`. `compileall` used an
external `PYTHONPYCACHEPREFIX`. Runtime probes used isolated
`FISHMESH_DATA_DIR` directories, so neither source assets nor package resources
were writable runtime targets.

## Strict TDD evidence

Each behavior change was observed failing before its implementation.

| Area | RED command and observed result | GREEN command and observed result |
| --- | --- | --- |
| TRANSFER, HELLO, SPRITE_CHUNK | `uv run pytest tests/test_message_validation.py tests/test_sprite_names.py -q` -> 33 failed, 93 passed | Same command -> 126 passed |
| Network handoff and bind cleanup | `uv run pytest tests/test_network_concurrency.py -q` -> 5 failed | `uv run pytest tests/test_network_concurrency.py tests/test_logging.py -q` -> 22 passed |
| Legacy migration | focused `tests/test_sprite_names.py` selection -> 4 failed | full `tests/test_sprite_names.py -q` -> 81 passed after symlink/reparse coverage |
| Bounded sprite worker lifecycle | `uv run pytest tests/test_sprite_worker.py tests/test_runtime_lifecycle.py -q` -> 5 failed, 4 passed | Same command -> 9 passed; combined worker/lifecycle/sprite regression -> 90 passed |
| Installed wheel resources | `uv run pytest tests/test_wheel_install.py -q` -> 1 failed because the installed runtime did not report 10 sprite types | Same command -> 1 passed with a no-source-CWD bounded runtime and unchanged install digest |
| Installed wheel audio | `uv run pytest tests/test_wheel_install.py -q` -> 1 failed at `assert audio.enabled` in the installed environment | Same command -> 1 passed; packaged `water.wav` enabled playback under dummy SDL, default startup logged `audio_enabled=True`, and the install digest stayed unchanged |
| V1 sprite frame ceiling | `uv run pytest tests/test_sprite_limits.py -q` -> 3 failed, 1 passed | Same command -> 4 passed with real normalized PNGs below and above 103,040 bytes plus worker recovery |
| Closed logging stream | focused closed-file reconfiguration test -> 1 failed with `ValueError: I/O operation on closed file` | `tests/test_logging.py tests/test_runtime_lifecycle.py -q` -> 23 passed |

An earlier full-suite attempt exposed a rate-limiter isolation issue; that test
now owns a fresh limiter and logger handler. Adding the audio logger later also
exposed a hard-coded test cleanup list: a handler retained a closed capture
stream, producing 9 failed and 195 passed. A real closed-file regression first
failed, then the reconfiguration recovery and shared logger list passed the
focused gate. The fresh full gate passes all 205 tests.

## Quality gate results

| Command | Result |
| --- | --- |
| `uv run ruff check src/fishmesh src/fish_demo tests scripts` | Exit 0; `All checks passed!` |
| `uv run ty check src/fishmesh src/fish_demo` | Exit 0; `All checks passed!` |
| `uv run pytest --cov=src --cov-report=term-missing` | Exit 0; 205 passed in 23.04 s; 61% whole-`src` coverage (2,685 statements, 1,034 missed) |
| `PYTHONPYCACHEPREFIX=/private/tmp/fishmesh-final-pycache-20260728-34fd60e uv run python -m compileall -q src` | Exit 0; no output |
| `uv run pytest tests/test_wheel_install.py -q` | Exit 0; 1 passed |
| `git diff --check` | Exit 0; no output |

The 2,685-statement denominator belongs to this code snapshot. The 1,034
missed count is the observed run result; bounded runtime and worker thread
timing can cause small run-to-run changes in which lines execute.

The wheel test copies only the build inputs into a temporary source tree,
builds and installs without editable-source access, loads and loops the packaged
`water.wav` under dummy SDL, starts `fishmesh-demo` with audio enabled for 0.2
seconds from an empty working directory, asserts 10 sprite types load, and
compares the complete site-packages content digest before and after runtime.

## Runtime entry-point and side-effect probes

Both entry points were run separately for one second with SDL dummy drivers,
different UDP ports, and isolated writable data roots:

```sh
uv run python src/main.py --port 6400 --expected-hosts 1 \
  --run-seconds 1 --windowed

uv run python -m fish_demo --port 6410 --expected-hosts 1 \
  --run-seconds 1 --windowed
```

Both exited 0 and logged `audio_enabled=True` and `sprite_count=10`. The
combined tracked configuration, source sprite, and package-resource digest was
`96a13c274faeb788b4f45d7032c0e5a2a1b8b4e5f4044b92b237d013055082b5`
before and after. `git status --short` was empty before and after.

## Hardened behavior

- Every TRANSFER float (`x`, `y`, `direction`, `speed`, `size`) must be finite
  and within an explicit V1 range. Malicious values are discarded at decode,
  so `math.cos(inf)` cannot terminate message handling.
- HELLO hostnames now truncate only at a valid UTF-8 boundary.
- SPRITE_CHUNK requires 1-224 chunks, an in-range index, and at most 460 data
  bytes per chunk. Conflicting totals clear the pending frame.
- A V1 sprite frame is capped at 103,040 bytes (224 x 460). Imports validate
  every normalized frame before creating destination files; the sender records
  and clears an oversized job, then continues serving later jobs.
- Network worker handoff captures immutable endpoint tuples under registry
  locking. Membership mutation and per-peer send errors cannot terminate the
  only listener thread. Constructor failure closes the UDP socket.
- Legacy migration rejects symlink/reparse roots and target directories,
  rejects source links or replacement races, and uses descriptor-bound,
  no-overwrite atomic creation. Repeated runs are idempotent.
- Sprite requests use one runtime-owned non-daemon worker with an eight-job
  queue. Duplicate peer/name jobs coalesce; overload is rejected. Enumeration,
  reads, chunking, and sends all occur off the render thread. Shutdown stops and
  joins this worker before closing the network socket.
- The wheel carries `water.wav` and ten package-owned, read-only default sprite
  frames. Audio loads through `importlib.resources`; imports, synchronization,
  and migration target platform user data or an explicit `FISHMESH_DATA_DIR`,
  never site-packages.

## Repository scope

The hardening range `d4c92f4..34fd60e` changes 32 files with 1,645 insertions
and 309 deletions. The complete M0-M1 range from the original `main` base changes
71 files with 6,890 insertions and 915 deletions. The isolated worktree was
clean at the code commit.

## Known limitations and pending evidence

- V1 still has no authentication, encryption, ACK/retry/deduplication envelope,
  or complete multi-frame manifest. The bounded queue limits unauthenticated
  request cost but does not authenticate requesters.
- V1 cannot represent a sprite frame above 103,040 bytes; oversized normalized
  imports are rejected rather than changing the wire format in M1.
- Discovery remains single-subnet IPv4 broadcast. Host IDs remain topology
  order dependent and topology remains one-dimensional.
- Whole-`src` coverage is measured but has no `fail-under` threshold. Pygame
  presentation modules remain the largest uncovered area.
- The GitHub Actions 3 OS x 3 Python matrix is declared but still needs a
  successful remote run. This local record does not claim native Linux or
  Windows execution.
- A real three-device LAN demonstration, including firewall and broadcast
  behavior, remains pending.

## Next plan boundary

M1 intentionally does not implement protocol V2, SWIM-inspired membership,
two-dimensional topology, the simulator, or the dashboard. Those remain in the
separately approved M2-M5 plans.
