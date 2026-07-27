from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

import message


@dataclass
class DummyFish:
    fish_id: int = 513
    x: float = 120.5
    y: float = 300.25
    direction: float = 0.0
    speed: float = 85.0
    size: float = 1.2
    color: tuple[int, int, int] = (12, 34, 56)
    fish_type: str = "JinYu"


def test_v1_header_is_eight_bytes() -> None:
    assert message.HEADER_SIZE == 8


def test_v1_message_inventory_has_all_nine_constants() -> None:
    assert {
        message.MSG_HELLO,
        message.MSG_ACK,
        message.MSG_HEARTBEAT,
        message.MSG_TOPOLOGY,
        message.MSG_TRANSFER,
        message.MSG_GOODBYE,
        message.MSG_SPRITE_PING,
        message.MSG_SPRITE_REQ,
        message.MSG_SPRITE_CHUNK,
    } == set(message.MSG_NAMES)
    assert len(message.MSG_NAMES) == 9


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


def test_v1_ack_uses_legacy_hello_alias() -> None:
    packet = message.pack_ack(2, "node-a", "192.168.1.10", 6000)
    header, payload = message.unpack_full(packet)
    assert message.pack_ack is message.pack_hello
    assert message.unpack_ack is message.unpack_hello
    assert header[0] == message.MSG_HELLO
    assert message.unpack_ack(payload) == {
        "hostname": "node-a",
        "ip": "192.168.1.10",
        "port": 6000,
    }


def test_v1_heartbeat_carries_sprite_types() -> None:
    packet = message.pack_heartbeat(1, sprite_types=["Fish A", "JinYu"])
    _, payload = message.unpack_full(packet)
    assert message.unpack_heartbeat(payload)["types"] == ["Fish A", "JinYu"]


def test_v1_topology_round_trip() -> None:
    hosts = [
        {"host_id": 1, "position": 0, "ip": "192.168.1.10", "port": 6000},
        {"host_id": 2, "position": 1, "ip": "192.168.1.11", "port": 6001},
    ]
    header, payload = message.unpack_full(message.pack_topology(3, hosts))
    assert header[0] == message.MSG_TOPOLOGY
    assert header[1] == 3
    assert message.unpack_topology(payload) == hosts


def test_v1_transfer_round_trip() -> None:
    header, payload = message.unpack_full(message.pack_transfer(2, DummyFish(), 1920))
    transferred = message.unpack_transfer(payload)
    assert header[0] == message.MSG_TRANSFER
    assert transferred["fish_id"] == 513
    assert transferred["x"] == pytest.approx(120.5)
    assert transferred["y"] == pytest.approx(300.25)
    assert transferred["direction"] == pytest.approx(0.0)
    assert transferred["speed"] == pytest.approx(85.0)
    assert transferred["size"] == pytest.approx(1.2)
    assert transferred["color"] == (12, 34, 56)
    assert transferred["fish_type"] == "JinYu"
    assert transferred["source_screen_w"] == 1920
    assert transferred["heading_right"] is True


def test_v1_goodbye_round_trip() -> None:
    header, payload = message.unpack_full(message.pack_goodbye(4))
    assert header[0] == message.MSG_GOODBYE
    assert header[1] == 4
    assert payload == b""


def test_v1_sprite_ping_round_trip() -> None:
    header, payload = message.unpack_full(message.pack_sprite_ping(5, ["Fish A", "JinYu"]))
    assert header[0] == message.MSG_SPRITE_PING
    assert message.unpack_sprite_ping(payload) == ["Fish A", "JinYu"]


def test_v1_sprite_request_round_trip() -> None:
    header, payload = message.unpack_full(message.pack_sprite_request(6, "Fish A"))
    assert header[0] == message.MSG_SPRITE_REQ
    assert message.unpack_sprite_request(payload) == "Fish A"


def test_v1_sprite_chunk_round_trip() -> None:
    header, payload = message.unpack_full(
        message.pack_sprite_chunk(7, "Fish A", 1, 3, 2, b"png-data")
    )
    assert header[0] == message.MSG_SPRITE_CHUNK
    assert message.unpack_sprite_chunk(payload) == {
        "name": "Fish A",
        "frame_index": 1,
        "total_chunks": 3,
        "chunk_index": 2,
        "data": b"png-data",
    }


def test_legacy_baseline_capture_reports_measured_facts(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    output = tmp_path / "legacy-m0.json"
    result = subprocess.run(
        [sys.executable, "scripts/capture_legacy_baseline.py", "--output", str(output)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    captured = json.loads(output.read_text(encoding="utf-8"))
    assert captured["schema_version"] == 1
    assert captured["message_header_bytes"] == 8
    assert captured["message_type_count"] == 9
    assert captured["sprite_type_count"] == 10
    assert captured["tracked_personal_paths"] == ["C:/Users/Athur/OneDrive/ͼƬ/OIP-C.png"]
    assert captured["source_lines"]["src/message.py"] > 0
