# FishMesh M0 legacy baseline

This document freezes observed V1 behavior before M1 defensive changes. It is a
baseline record, not a statement that the listed behaviors are acceptable.

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

`tests/legacy/test_message_v1.py` characterizes the V1 packet header and round
trips for HELLO, HEARTBEAT, TOPOLOGY, TRANSFER, GOODBYE, SPRITE_PING,
SPRITE_REQ, and SPRITE_CHUNK.

## Confirmed defects and M1 actions

| Capability | Current behavior | Evidence | M1 action |
| --- | --- | --- | --- |
| Malformed packet handling | Short or truncated UDP data can raise `struct.error` while the main loop invokes `unpack_full` without a decode guard. | `src/message.py:37-48`; `src/main.py:152-157` | Add typed, fail-closed packet validation and discard malformed datagrams. |
| Sprite requests | A requested name remains in `reg._pending_requests`; no completion or timeout removes it, so an incomplete/lost transfer suppresses later retries. | `src/main.py:206-214` and matching sprite-ping flow at `src/main.py:274-279` | Replace the permanent set with a retryable request tracker. |
| Host identities | Rebuilding topology reassigns each host's `host_id` according to sorted peers, so host IDs are mutable. | `src/network.py:149-156` | Preserve compatibility in M1; define stable identity semantics in the later protocol migration. |
| Network sends on the render thread | Incoming message handling is called by the main loop and directly calls `net.send`/`net.broadcast`; transfers also send directly. | `src/main.py:58-69`, `src/main.py:512-521`, `src/main.py:166-181` | Move sprite and control sends behind a worker/queue without changing visible behavior. |
| Tracked personal path | The tracked background config contains a machine-specific Windows OneDrive path: `C:/Users/Athur/OneDrive/ͼƬ/OIP-C.png`. | `config.ini:20-22`; capture field `tracked_personal_paths` | Replace it with portable example configuration during M1. |
