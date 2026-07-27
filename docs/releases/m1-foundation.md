# FishMesh M1 Foundation Release Verification

## Candidate status

- Verification date: 2026-07-27 (Asia/Shanghai).
- Branch: `codex/fishmesh-m0-m1`.
- Verification commit: `ffb21ef2fd57a430ef0f3f5b6edae4a6178086a6`.
- Base commit: `603f7d31c795bac58740765b041c6bacc26f8659` (`main`).
- Release designation: `m1-foundation` tag candidate. No Git tag was created by this verification.

## Local environment

| Component | Verified value |
| --- | --- |
| Operating system | macOS 26.5.2, build 25F84, arm64 |
| Python | 3.12.13, Clang 17.0.0 (`clang-1700.6.3.2`) |
| Virtual environment interpreter | `.venv/bin/python3` in the isolated worktree |
| uv | 0.11.28 (Homebrew 2026-07-07, aarch64-apple-darwin) |
| pygame / SDL | pygame 2.6.1 / SDL 2.28.4 |
| Ruff | 0.16.0 |
| ty | 0.0.63 (`46f4915e6`, 2026-07-23) |
| pytest / pytest-cov | 8.4.2 / 6.3.0 |
| Git | 2.50.1 (Apple Git-155) |

All Python verification commands used `PYTHONDONTWRITEBYTECODE=1`. The
`compileall` command additionally placed its cache under `/private/tmp`, so
verification did not write bytecode into the source tree.

## Quality gate results

The following commands were run serially from a clean isolated worktree.

| Command | Result | Observed duration |
| --- | --- | ---: |
| `uv run ruff check src/fishmesh src/fish_demo tests scripts` | Exit 0; `All checks passed!` | 3.3 s |
| `uv run ty check src/fishmesh src/fish_demo` | Exit 0; `All checks passed!` | 2.9 s |
| `uv run pytest --cov=src --cov-report=term-missing` | Exit 0; 148 passed; 55% whole-`src` coverage (2,404 statements, 1,087 missed) | 20.99 s reported by pytest |
| `PYTHONPYCACHEPREFIX=/private/tmp/fishmesh-task11-pycache-20260727T1906 uv run python -m compileall -q src` | Exit 0; no output | 3.6 s |
| `git diff --check` | Exit 0; no output | 0.1 s |
| `uv run pytest tests/test_wheel_install.py -v` | Exit 0; isolated wheel build, install, console load, and runtime-module imports passed (1 test) | 16.13 s reported by pytest |

The wheel test builds from a temporary source tree, installs without editable
source access, clears project import paths, and exercises the installed
`fishmesh-demo` console entry point.

## Runtime entry-point checks

Both supported entry points were run separately with SDL dummy video and
audio drivers:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  uv run python src/main.py \
  --expected-hosts 1 --run-seconds 1 --windowed --no-audio

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 \
  uv run python -m fish_demo \
  --expected-hosts 1 --run-seconds 1 --windowed --no-audio
```

Each command exited 0, loaded 10 sprite types, reached `Mesh target: 1 hosts`,
and shut down after the bounded run. The SDL dummy driver did not create a
display-backed visible window. UDP ports 6000-6009 were unbound before and
after the runs.

The following side-effect checks also matched before and after both entry
points:

- `config.ini` and `config.example.ini` SHA-256:
  `6fb2a9dab242f2d0f19c0423c274deb09939074afafb0cf2bb5e42aaf88d239d`;
- canonical sprite file-inventory SHA-256:
  `757bd739dc08c9429d08aa9d9137590f5165373744561278554ce09f7219f228`;
- exactly 10 canonical sprite type directories remained;
- the obsolete `assets/fish_sprites/Free Fish Icons` sentinel was not created;
- `git status --short` remained empty.

## Verification hygiene correction

The first release-gate attempt exposed two deterministic repository side
effects. Thirteen generated `.pyc` files were tracked and ordinary imports
rewrote three of them. Legacy sprite migration also copied 18 additional
frames into an already-populated canonical sprite tree.

Commit `ffb21ef` removes all tracked bytecode, adds a repository contract that
rejects tracked `.pyc`/`__pycache__` paths, and makes legacy migration skip an
already-populated canonical tree while preserving migration into an empty
tree. The migration and bytecode contracts were observed failing before the
fix and passing afterward. The 18 generated frames were individually verified
as untracked byte-for-byte copies of the retained legacy source assets before
being removed. The complete gate above was then rerun from the beginning.

## Repository scope

Compared with the merge base on `main`, M0-M1 changes 55 planned paths with
5,349 insertions and 811 deletions. The deletions include the 13 generated
bytecode artifacts. The isolated worktree was clean after verification. A
read-only check of the original checkout confirmed its pre-existing modified
and deleted files were unchanged by this worktree.

## Known limitations and pending evidence

- V1 has no authentication, encryption, ACK/retry/deduplication envelope, or
  end-to-end reliable resource transfer. Its sprite format has no complete
  multi-frame manifest.
- Discovery remains single-subnet IPv4 broadcast. Host IDs remain dependent on
  topology ordering, and M1 topology remains one-dimensional.
- Fish-transfer control packets still use the render-loop UDP send path; M1
  moved heartbeat and sprite payload work off that path.
- Whole-`src` coverage is measured but has no `fail-under` threshold. Legacy
  pygame presentation modules remain the largest uncovered area.
- The GitHub Actions 3 OS x 3 Python matrix is declared but still requires a
  successful remote run. This local verification does not claim native Linux
  or Windows execution.
- A real three-device LAN demonstration, including firewall and broadcast
  behavior, remains pending.

## Next approved plan boundary

M1 intentionally defers protocol V2, SWIM-inspired membership,
two-dimensional topology, the experiment simulator, and the monitoring
dashboard. Subsequent work must remain in separately approved plans:

1. **M2 Protocol V2:** versioned envelope, stable UUID/session identity,
   ACK/retry/deduplication, reliable resource transfer, bounded queues, and a
   V1 compatibility adapter.
2. **M3 Cluster Runtime:** SWIM-inspired membership, two-dimensional layout,
   migration ownership state machine, rollback, and convergence tests.
3. **M4 Experiment Platform:** multi-process orchestration, deterministic fault
   injection, metrics, simulator/dashboard views, and JSON/CSV reports.
4. **M5 Portfolio Release:** installers, real three-device lab protocol,
   demonstration video, public documentation, and release packaging.
5. **M6+ Research Extensions:** one separately approved experimental question
   per plan.
