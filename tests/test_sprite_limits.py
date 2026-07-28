from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import pygame
import pytest

import fish_demo.network_handlers as network_handlers
import message
import sprite_manager as sprite_module
from fishmesh.request_tracker import RequestTracker
from fishmesh.sprite_names import InvalidSpriteName
from sprite_manager import SpriteManager


def _save_surface(path: Path, rgba: bytes) -> None:
    surface = pygame.image.frombytes(rgba, (256, 256), "RGBA")
    pygame.image.save(surface, path)


def test_v1_frame_limit_accepts_boundary_and_rejects_one_byte_over() -> None:
    at_limit = b"x" * 103_040

    assert sprite_module.validate_sprite_frame_bytes(at_limit) is at_limit
    with pytest.raises(InvalidSpriteName, match="103040"):
        sprite_module.validate_sprite_frame_bytes(at_limit + b"x")


def test_import_accepts_real_normalized_png_below_v1_limit(tmp_path: Path) -> None:
    pygame.display.set_mode((1, 1))
    source = tmp_path / "source"
    sprite_root = tmp_path / "sprites"
    source.mkdir()
    _save_surface(source / "solid.png", bytes((10, 20, 30, 255)) * (256 * 256))
    manager = SpriteManager.__new__(SpriteManager)
    manager.SPRITE_DIR = sprite_root
    manager._scan_sprites_dir = lambda: None

    assert manager.import_sprites(source, "Solid") is True

    imported = sprite_root / "Solid" / "Fish-1.png"
    assert imported.is_file()
    assert imported.stat().st_size <= 103_040


def test_import_rejects_real_normalized_png_over_v1_limit_without_partial_write(
    tmp_path: Path,
) -> None:
    pygame.display.set_mode((1, 1))
    source = tmp_path / "source"
    sprite_root = tmp_path / "sprites"
    source.mkdir()
    noise = random.Random(0).randbytes(256 * 256 * 4)
    _save_surface(source / "noise.png", noise)
    manager = SpriteManager.__new__(SpriteManager)
    manager.SPRITE_DIR = sprite_root
    manager._scan_sprites_dir = lambda: None

    with pytest.raises(InvalidSpriteName, match="103040"):
        manager.import_sprites(source, "Noise")

    assert not (sprite_root / "Noise" / "Fish-1.png").exists()


def test_worker_records_oversized_frame_rejection_then_serves_next_job(
    tmp_path: Path,
    caplog,
) -> None:
    root = tmp_path / "sprites"
    oversized = root / "Oversized"
    valid = root / "Valid"
    oversized.mkdir(parents=True)
    valid.mkdir()
    (oversized / "Fish-1.png").write_bytes(b"x" * 103_041)
    (valid / "Fish-1.png").write_bytes(b"valid")
    sent = []
    valid_sent = False

    class Net:
        def send(self, ip: str, port: int, packet: bytes) -> None:
            sent.append((ip, port, packet))

    logger = logging.getLogger("fish_demo.network_handlers")
    original_propagate = logger.propagate
    logger.addHandler(caplog.handler)
    logger.propagate = False
    worker = network_handlers.SpriteSendWorker(root, Net(), max_pending=1)
    try:
        with caplog.at_level(logging.WARNING):
            assert worker.submit("192.0.2.10", 6200, 1, "Oversized") is True
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not any(
                getattr(record, "event", None) == "sprite_send_rejected"
                for record in caplog.records
            ):
                time.sleep(0.005)
            assert worker.submit("192.0.2.10", 6200, 1, "Valid") is True
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not sent:
                time.sleep(0.005)
            valid_sent = bool(sent)
    finally:
        worker.stop()
        logger.removeHandler(caplog.handler)
        logger.propagate = original_propagate

    rejected = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "sprite_send_rejected"
    ]
    assert len(rejected) == 1
    assert rejected[0].frame_bytes == 103_041
    assert valid_sent is True


def test_oversized_only_type_is_not_advertised_or_retried(
    tmp_path: Path,
) -> None:
    pygame.display.set_mode((1, 1))
    root = tmp_path / "sprites"
    oversized = root / "OversizedOnly"
    oversized.mkdir(parents=True)
    (oversized / "Fish-1.png").write_bytes(b"x" * 103_041)
    provider = SpriteManager.__new__(SpriteManager)
    provider.SPRITE_DIR = root
    provider._scan_sprites_dir()

    assert provider.get_types() == []

    now = [100.0]
    tracker = RequestTracker(retry_after=1.0, clock=lambda: now[0])
    sent: list[bytes] = []

    class Net:
        port = 6201

        def send(self, _ip: str, _port: int, packet: bytes) -> None:
            sent.append(packet)

    class Registry:
        my_id = 2
        my_hostname = "receiver"
        my_ip = "192.0.2.20"
        my_key = "192.0.2.20:6201"
        hosts = {"192.0.2.10:6200": object()}

        def heartbeat(self, *_args, **_kwargs) -> None:
            pass

    receiver = type("ReceiverSprites", (), {"get_types": lambda _self: []})()
    packets = (
        message.pack_heartbeat(1, sprite_types=provider.get_types()),
        message.pack_sprite_ping(1, provider.get_types()),
    )
    for _ in range(3):
        for packet in packets:
            network_handlers.handle_network_message(
                packet,
                ("192.0.2.10", 6200),
                Net(),
                Registry(),
                [],
                800,
                600,
                receiver,
                object(),
                request_tracker=tracker,
            )
        now[0] += 2.0

    assert sent == []
    assert tracker.should_request("OversizedOnly") is True


def test_mixed_type_is_advertised_and_worker_sends_only_legal_frames(
    tmp_path: Path,
) -> None:
    pygame.display.set_mode((1, 1))
    root = tmp_path / "sprites"
    mixed = root / "Mixed"
    mixed.mkdir(parents=True)
    (mixed / "Fish-1.png").write_bytes(b"x" * 103_041)
    (mixed / "Fish-2.png").write_bytes(b"valid")
    provider = SpriteManager.__new__(SpriteManager)
    provider.SPRITE_DIR = root
    provider._scan_sprites_dir()

    assert provider.get_types() == ["Mixed"]
    _, heartbeat_payload = message.unpack_full(
        message.pack_heartbeat(1, sprite_types=provider.get_types())
    )
    _, ping_payload = message.unpack_full(message.pack_sprite_ping(1, provider.get_types()))
    assert message.unpack_heartbeat(heartbeat_payload)["types"] == ["Mixed"]
    assert message.unpack_sprite_ping(ping_payload) == ["Mixed"]

    sent: list[bytes] = []

    class Net:
        def send(self, _ip: str, _port: int, packet: bytes) -> None:
            sent.append(packet)

    worker = network_handlers.SpriteSendWorker(root, Net(), max_pending=1)
    try:
        assert worker.submit("192.0.2.10", 6200, 1, "Mixed") is True
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and not sent:
            time.sleep(0.005)
    finally:
        worker.stop()

    chunks = []
    for packet in sent:
        _, payload = message.unpack_full(packet)
        chunks.append(message.unpack_sprite_chunk(payload))
    assert [(chunk["frame_index"], chunk["data"]) for chunk in chunks] == [(1, b"valid")]
