# FishMesh M0 legacy baseline

This document freezes observed V1 behavior before M1 defensive changes. It is a
baseline record, not a statement that the listed behaviors are acceptable. The
measurements were taken from code commit `c9a04771058585300e0c470de7507031cdec7842`
and recorded by baseline commit `9f690d2de23560047b20fb61887770c7ac125ea8`.

## Capture command and environment

```sh
uv run python scripts/capture_legacy_baseline.py --output /tmp/fishmesh-legacy-m0.json
```

Captured with Python 3.12.13 on `macOS-26.5.2-arm64-arm-64bit`. The capture
reports schema version 1, an 8-byte V1 header, 9 message types, and 10 sprite
type directories. It reads files only; it does not load or save runtime
configuration.

## Current module inventory

| Module | Lines |
| --- | ---: |
| `src/main.py` | 649 |
| `src/message.py` | 289 |
| `src/network.py` | 280 |
| `src/sprite_manager.py` | 276 |
| `src/background_manager.py` | 240 |
| `src/fish_entity.py` | 225 |
| `src/renderer.py` | 188 |
| `src/sprite_sync.py` | 137 |
| `src/ui.py` | 565 |
| `src/audio_manager.py` | 48 |
| `src/config.py` | 26 |

`tests/legacy/test_message_v1.py` explicitly inventories all nine V1 constants
and characterizes the packet header plus HELLO, ACK (the legacy HELLO pack/unpack
alias), HEARTBEAT, TOPOLOGY, TRANSFER, GOODBYE, SPRITE_PING, SPRITE_REQ, and
SPRITE_CHUNK round trips.

## Confirmed defects and M1 actions

| Capability | Current behavior | Evidence | M1 action |
| --- | --- | --- | --- |
| Malformed packet handling | Short or truncated UDP data can raise `struct.error` while the main loop invokes `unpack_full` without a decode guard. | `src/message.py:37-48`; `src/main.py:152-157` | Add typed, fail-closed packet validation and discard malformed datagrams. |
| Sprite requests | A requested name remains in `reg._pending_requests`; no completion or timeout removes it, so an incomplete/lost transfer suppresses later retries. | `src/main.py:206-214` and matching sprite-ping flow at `src/main.py:274-279` | Replace the permanent set with a retryable request tracker. |
| Host identities | Rebuilding topology reassigns each host's `host_id` according to sorted peers, so host IDs are mutable. | `src/network.py:149-156` | Preserve compatibility in M1; define stable identity semantics in the later protocol migration. |
| Network sends on the render thread | Incoming message handling is called by the main loop and directly calls `net.send`/`net.broadcast`; transfers also send directly. | `src/main.py:58-69`, `src/main.py:512-521`, `src/main.py:166-181` | Move sprite and control sends behind a worker/queue without changing visible behavior. |
| Tracked personal path | The tracked background config contains a machine-specific Windows OneDrive path: `C:/Users/Athur/OneDrive/ͼƬ/OIP-C.png`. | `config.ini:20-22`; capture field `tracked_personal_paths` | Replace it with portable example configuration during M1. |

## Historical M1 result

This section preserves the result as it stood at `5827fc947e720e956d00d0551f5d4cc6f7e0c8f4`;
it is not the current branch result. Measured on 2026-07-27 with Python 3.12.13
(Clang 17.0.0), uv 0.11.28,
and macOS 26.5.2 build 25F84 on arm64. The complete command
`uv run pytest --cov=src --cov-report=term-missing` collected and passed 145
tests. Coverage was 55% (2,396 statements, 1,085 missed). This is the measured
whole-`src` value: pygame-heavy and legacy presentation modules remain in the
denominator, and M1 does not define or enforce a coverage threshold.

### Interpreter and platform support

| Platform | Python | Verification status |
| --- | --- | --- |
| macOS 26.5.2 arm64 | 3.12.13 | Locally verified: dependency sync, Ruff, ty, 145 tests with coverage, both headless entry points, compileall, and diff checks. |
| Ubuntu latest | 3.11, 3.12, 3.13 | Declared in GitHub Actions; pending a successful remote CI run. |
| macOS latest | 3.11, 3.12, 3.13 | Declared in GitHub Actions; matrix combinations pending a successful remote CI run. |
| Windows latest | 3.11, 3.12, 3.13 | Declared in GitHub Actions; pending a successful remote CI run, including the complete suite and an explicit native Windows sprite-safety test pass. |

### Resolved defects

- Malformed, truncated, and unknown V1 datagrams now fail closed and are logged
  without terminating the application loop.
- Missing sprite requests can be retried after a deadline until at least one
  complete frame is stored.
- Sprite names, reads, imports, temporary writes, and atomic replacement are
  constrained to verified resource directories, including a Windows-native
  directory guard path.
- The tracked configuration is portable UTF-8 data without a personal absolute
  path; diagnostic CLI overrides do not persist.
- Both `python src/main.py` and `python -m fish_demo` support deterministic
  headless startup and clean shutdown. Runtime boundaries now emit structured,
  rate-limited log events.
- Heartbeats and sprite payload transfer no longer perform their bulk sends on
  the render thread.

### Remaining limitations

- V1 has no authentication, encryption, ACK/deduplication, or complete
  multi-frame manifest. M1 cannot detect a missing later frame after a sprite
  type becomes locally visible.
- Host IDs remain topology-order dependent, discovery is single-subnet IPv4
  broadcast, and the topology is one-dimensional.
- Fish transfer control packets still call the UDP send path from the render
  loop; only heartbeat and sprite payload work has been moved off that path.
- The 3 x 3 CI matrix is a declaration until GitHub Actions reports successful
  jobs. This local run does not claim native Windows/Linux or a real three-host
  LAN verification.

## Final hardening result

The 2026-07-28 hardening code snapshot is
`34fd60e3135c8904f71595188c27f2fdeb25e867`. Its fresh local gate collected and
passed 205 tests. Whole-`src` coverage is 61% (2,685 statements, 1,034 missed in
the observed run; bounded thread timing can vary the missed count slightly).
This supersedes the historical test and coverage totals above without rewriting
the earlier evidence. Remote 3 OS x 3 Python CI and a real three-machine LAN run
remain pending.
