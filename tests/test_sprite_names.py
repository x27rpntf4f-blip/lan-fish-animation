from __future__ import annotations

from pathlib import Path

import pytest

import main
import message
from fishmesh.request_tracker import RequestTracker
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


@pytest.mark.parametrize(
    "value",
    [
        "bad<name",
        "bad>name",
        'bad"name',
        "bad:name",
        "bad|name",
        "bad?name",
        "bad*name",
        "Fish.",
        "Fish. ",
        "CON",
        "con.txt",
        "PRN.png",
        "AUX",
        "NUL.data",
        "COM1",
        "com9.log",
        "LPT1",
        "lpt9.png",
    ],
)
def test_windows_unsafe_sprite_names_are_rejected(value: str) -> None:
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name(value)


def test_sprite_name_utf8_encoding_must_fit_v1_without_truncation() -> None:
    emoji_boundary = "🐟" * 63
    chinese_name = "鱼" * 64

    assert validate_sprite_name(emoji_boundary) == emoji_boundary
    assert validate_sprite_name(chinese_name) == chinese_name
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name("🐟" * 64)

    _, payload = message.unpack_full(message.pack_sprite_request(1, emoji_boundary))
    assert message.unpack_sprite_request(payload) == emoji_boundary


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


def test_existing_frame_symlink_is_replaced_without_overwriting_target(tmp_path: Path) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_dir = sprite_root / "Purple"
    outside = tmp_path / "outside.png"
    sprite_dir.mkdir(parents=True)
    outside.write_bytes(b"outside-secret")
    destination = sprite_dir / "Fish-1.png"
    destination.symlink_to(outside)
    manager = SpriteSyncManager(sprite_root)

    assert manager.feed_chunk(
        {
            "name": "Purple",
            "frame_index": 0,
            "total_chunks": 1,
            "chunk_index": 0,
            "data": b"safe-frame",
        }
    )

    assert outside.read_bytes() == b"outside-secret"
    assert not destination.is_symlink()
    assert destination.read_bytes() == b"safe-frame"


def test_failed_frame_write_clears_completed_pending_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = SpriteSyncManager(tmp_path)

    def fail_save(_name: str, _frame_index: int, _data: bytes) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(manager, "_save_frame", fail_save)

    with pytest.raises(OSError, match="disk full"):
        manager.feed_chunk(
            {
                "name": "Purple",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"frame",
            }
        )

    assert manager.pending_count() == 0


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


def test_local_import_replaces_frame_symlink_without_overwriting_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    sprite_root = tmp_path / "sprites"
    destination_dir = sprite_root / "Purple"
    outside = tmp_path / "outside.png"
    source.mkdir()
    destination_dir.mkdir(parents=True)
    (source / "frame.png").write_bytes(b"not-a-real-png")
    outside.write_bytes(b"outside-secret")
    destination = destination_dir / "Fish-1.png"
    destination.symlink_to(outside)
    manager = SpriteManager.__new__(SpriteManager)
    manager.SPRITE_DIR = str(sprite_root)
    manager._scan_sprites_dir = lambda: None

    assert manager.import_sprites(source, "Purple") is True

    assert outside.read_bytes() == b"outside-secret"
    assert not destination.is_symlink()
    assert destination.read_bytes() == b"not-a-real-png"


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


def test_sprite_data_sender_rejects_frame_symlink_without_reading_target(tmp_path: Path) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_dir = sprite_root / "Purple"
    outside = tmp_path / "secret.png"
    sprite_dir.mkdir(parents=True)
    outside.write_bytes(b"outside-secret")
    (sprite_dir / "Fish-1.png").symlink_to(outside)
    sprite_manager = type("SpriteManagerDouble", (), {"SPRITE_DIR": str(sprite_root)})()

    class NetDouble:
        def __init__(self) -> None:
            self.sent: list[tuple[object, ...]] = []

        def send(self, *args: object) -> None:
            self.sent.append(args)

    net = NetDouble()

    with pytest.raises(InvalidSpriteName):
        main._send_sprite_data_async(sprite_manager, net, "127.0.0.1", 6200, 1, "Purple")

    assert net.sent == []


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


def test_network_handler_clears_pending_when_sprite_directory_is_symlink(tmp_path: Path) -> None:
    sprite_root = tmp_path / "sprites"
    outside = tmp_path / "outside"
    sprite_root.mkdir()
    outside.mkdir()
    (sprite_root / "Linked").symlink_to(outside, target_is_directory=True)
    sync_manager = SpriteSyncManager(sprite_root)
    packet = message.pack_sprite_chunk(1, "Linked", 0, 1, 0, b"not-safe")

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
    assert list(outside.iterdir()) == []


def test_network_handler_marks_canonical_sprite_name_complete(tmp_path: Path) -> None:
    tracker = RequestTracker(retry_after=60)
    tracker.mark_requested("Purple")
    sync_manager = SpriteSyncManager(tmp_path)
    packet = message.pack_sprite_chunk(1, " Purple ", 0, 1, 0, b"frame")

    class SpriteManagerDouble:
        def _scan_sprites_dir(self) -> None:
            pass

        def get_types(self) -> list[str]:
            return ["Purple"]

    main.handle_network_message(
        packet,
        ("127.0.0.1", 6200),
        object(),
        object(),
        [],
        800,
        600,
        SpriteManagerDouble(),
        sync_manager,
        tracker,
    )

    assert tracker.should_request("Purple")


def test_ui_import_callback_turns_invalid_name_into_failed_import(capsys) -> None:
    class SpriteManagerDouble:
        def import_sprites(self, _source: str, _name: str) -> bool:
            raise InvalidSpriteName("unsafe")

    class PanelDouble:
        def refresh_fish_types(self) -> None:
            raise AssertionError("failed import must not refresh UI state")

        def set_bg_type(self, _bg_type: str) -> None:
            raise AssertionError("failed import must not refresh UI state")

    background = type("BackgroundDouble", (), {"bg_type": "gradient"})()

    assert main._handle_sprite_import(
        SpriteManagerDouble(), PanelDouble(), background, "CON", "/tmp/source"
    ) is False
    assert "invalid sprite name" in capsys.readouterr().out.lower()
