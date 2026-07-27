from __future__ import annotations

from pathlib import Path

import pytest

import main
import message
from fishmesh.sprite_names import InvalidSpriteName, validate_sprite_name
from sprite_manager import SpriteManager
from sprite_sync import SpriteSyncManager


@pytest.mark.parametrize("value", ["Fish A", "JinYu", "purple-2", "锦鲤", "two  spaces"])
def test_valid_sprite_names_are_preserved(value: str) -> None:
    assert validate_sprite_name(value) == value


def test_sprite_names_are_trimmed_and_normalized_to_nfc() -> None:
    assert validate_sprite_name("  JinYu  ") == "JinYu"
    assert validate_sprite_name(" Cafe\N{COMBINING ACUTE ACCENT} ") == "Café"


@pytest.mark.parametrize(
    "value",
    ["", "   ", ".", "..", "../escape", "a/b", "a\\b", "\x00bad", "bad\x7fname"],
)
def test_unsafe_sprite_names_are_rejected(value: str) -> None:
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name(value)


def test_sprite_names_must_be_at_most_64_characters_after_normalization() -> None:
    assert validate_sprite_name("a" * 64) == "a" * 64
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name("a" * 65)


def test_complete_chunk_is_written_below_sprite_root(tmp_path: Path) -> None:
    manager = SpriteSyncManager(tmp_path)

    complete = manager.feed_chunk(
        {
            "name": " Purple ",
            "frame_index": 0,
            "total_chunks": 1,
            "chunk_index": 0,
            "data": b"png-data",
        }
    )

    assert complete is True
    assert (tmp_path / "Purple" / "Fish-1.png").read_bytes() == b"png-data"


def test_unsafe_chunk_name_never_creates_pending_state_or_files(tmp_path: Path) -> None:
    manager = SpriteSyncManager(tmp_path)

    with pytest.raises(InvalidSpriteName):
        manager.feed_chunk(
            {
                "name": "../escape",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"not-safe",
            }
        )

    assert manager.pending_count() == 0
    assert not (tmp_path.parent / "escape").exists()
    assert list(tmp_path.rglob("*")) == []


def test_existing_symlink_cannot_redirect_completed_chunk(tmp_path: Path) -> None:
    sprite_root = tmp_path / "sprites"
    outside = tmp_path / "outside"
    sprite_root.mkdir()
    outside.mkdir()
    (sprite_root / "Linked").symlink_to(outside, target_is_directory=True)
    manager = SpriteSyncManager(sprite_root)

    with pytest.raises(InvalidSpriteName):
        manager.feed_chunk(
            {
                "name": "Linked",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"not-safe",
            }
        )

    assert list(outside.iterdir()) == []


def test_local_import_rejects_path_escape_before_creating_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    sprite_root = tmp_path / "sprites"
    source.mkdir()
    sprite_root.mkdir()
    manager = SpriteManager.__new__(SpriteManager)
    manager.SPRITE_DIR = str(sprite_root)

    with pytest.raises(InvalidSpriteName):
        manager.import_sprites(source, "../escape")

    assert not (tmp_path / "escape").exists()


def test_sprite_data_sender_rejects_path_escape_before_reading(tmp_path: Path) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_root.mkdir()
    sprite_manager = type("SpriteManagerDouble", (), {"SPRITE_DIR": str(sprite_root)})()

    with pytest.raises(InvalidSpriteName):
        main._send_sprite_data_async(
            sprite_manager,
            object(),
            "127.0.0.1",
            6200,
            1,
            "../escape",
        )


def test_unsafe_remote_type_is_not_requested() -> None:
    class NetDouble:
        def __init__(self) -> None:
            self.sent: list[tuple[object, ...]] = []

        def send(self, *args: object) -> None:
            self.sent.append(args)

    class TrackerDouble:
        def should_request(self, _name: str) -> bool:
            return True

        def mark_requested(self, _name: str) -> None:
            raise AssertionError("unsafe name must not be tracked")

    net = NetDouble()
    registry = type("RegistryDouble", (), {"my_id": 1})()
    sprite_manager = type("SpriteManagerDouble", (), {"get_types": lambda _self: []})()

    main._request_missing_sprites(
        ["../escape"],
        "127.0.0.1",
        6200,
        net,
        registry,
        sprite_manager,
        TrackerDouble(),
    )

    assert net.sent == []


def test_network_handler_discards_unsafe_chunk_without_raising(tmp_path: Path) -> None:
    packet = message.pack_sprite_chunk(1, "../escape", 0, 1, 0, b"not-safe")
    sync_manager = SpriteSyncManager(tmp_path)

    main.handle_network_message(
        packet,
        ("127.0.0.1", 6200),
        object(),
        object(),
        [],
        800,
        600,
        object(),
        sync_manager,
    )

    assert sync_manager.pending_count() == 0
    assert list(tmp_path.rglob("*")) == []
