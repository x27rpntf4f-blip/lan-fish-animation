from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path

import pytest

import fishmesh.sprite_names as sprite_names_module
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
        "COM¹",
        "com².txt",
        "COM³.log",
        "LPT1",
        "lpt9.png",
        "LPT¹",
        "lpt².txt",
        "LPT³.log",
        "CONIN$",
        "conout$.txt",
    ],
)
def test_windows_unsafe_sprite_names_are_rejected(value: str) -> None:
    with pytest.raises(InvalidSpriteName):
        validate_sprite_name(value)


@pytest.mark.parametrize("value", ["锦鲤²", "COM🐟", "LPT十"])
def test_non_reserved_unicode_sprite_names_remain_valid(value: str) -> None:
    assert validate_sprite_name(value) == value


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


def test_conflicting_chunk_total_clears_pending_frame(tmp_path: Path) -> None:
    manager = SpriteSyncManager(tmp_path)
    first = {
        "name": "Purple",
        "frame_index": 0,
        "total_chunks": 2,
        "chunk_index": 0,
        "data": b"first",
    }
    conflicting = first | {"total_chunks": 3, "chunk_index": 1, "data": b"conflict"}

    assert manager.feed_chunk(first) is False
    with pytest.raises(ValueError, match="conflicting"):
        manager.feed_chunk(conflicting)

    assert manager.pending_count() == 0
    assert list(tmp_path.rglob("*.png")) == []


@pytest.mark.parametrize(
    "info",
    [
        {
            "name": "Purple",
            "frame_index": 0,
            "total_chunks": 0,
            "chunk_index": 0,
            "data": b"x",
        },
        {
            "name": "Purple",
            "frame_index": 0,
            "total_chunks": 225,
            "chunk_index": 0,
            "data": b"x",
        },
        {
            "name": "Purple",
            "frame_index": 0,
            "total_chunks": 1,
            "chunk_index": 1,
            "data": b"x",
        },
        {
            "name": "Purple",
            "frame_index": 0,
            "total_chunks": 1,
            "chunk_index": 0,
            "data": b"x" * 461,
        },
    ],
    ids=["zero-total", "too-many-chunks", "index-out-of-range", "oversized-data"],
)
def test_invalid_chunk_fields_do_not_allocate_pending_state(tmp_path: Path, info: dict) -> None:
    manager = SpriteSyncManager(tmp_path)

    with pytest.raises(ValueError):
        manager.feed_chunk(info)

    assert manager.pending_count() == 0


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


def test_swapped_temporary_entry_is_rejected_without_touching_victim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_dir = sprite_root / "Purple"
    victim = tmp_path / "victim.png"
    sprite_dir.mkdir(parents=True)
    victim.write_bytes(b"victim")
    manager = SpriteSyncManager(sprite_root)
    original_fsync = os.fsync
    attacked = False

    def swap_temp_entry(descriptor: int) -> None:
        nonlocal attacked
        if not attacked:
            temporary = next(sprite_dir.glob(".Fish-1.png.*.png"))
            temporary.unlink()
            temporary.symlink_to(victim)
            attacked = True
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", swap_temp_entry)

    with pytest.raises(InvalidSpriteName):
        manager.feed_chunk(
            {
                "name": "Purple",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"frame",
            }
        )

    assert attacked
    assert manager.pending_count() == 0
    assert victim.read_bytes() == b"victim"
    assert not (sprite_dir / "Fish-1.png").exists()


def test_parent_swap_after_final_validation_is_rejected_and_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_dir = sprite_root / "Purple"
    moved_dir = tmp_path / "moved-purple"
    sprite_dir.mkdir(parents=True)
    manager = SpriteSyncManager(sprite_root)
    original_replace = os.replace
    attacked = False

    def swap_parent_then_replace(src, dst, *args, **kwargs):
        nonlocal attacked
        if not attacked:
            sprite_dir.rename(moved_dir)
            sprite_dir.symlink_to(moved_dir, target_is_directory=True)
            attacked = True
        return original_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", swap_parent_then_replace)

    with pytest.raises(InvalidSpriteName):
        manager.feed_chunk(
            {
                "name": "Purple",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"frame",
            }
        )

    assert attacked
    assert manager.pending_count() == 0
    assert not (moved_dir / "Fish-1.png").exists()


def test_no_dirfd_fallback_rejects_before_double_parent_swap_can_write_outside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sprite_root = tmp_path / "sprites"
    sprite_dir = sprite_root / "Purple"
    moved_app = tmp_path / "moved-app"
    decoy = tmp_path / "decoy"
    sprite_dir.mkdir(parents=True)
    decoy.mkdir()
    manager = SpriteSyncManager(sprite_root)
    real_os = os
    original_replace = os.replace
    original_snapshot = sprite_names_module._directory_snapshot
    snapshot_calls = 0
    replace_calls = 0

    class NoDirFdOs:
        name = "java"

        def __getattr__(self, attribute: str):
            return getattr(real_os, attribute)

    def first_parent_swap(src, dst, *args, **kwargs):
        nonlocal replace_calls
        replace_calls += 1
        sprite_dir.rename(moved_app)
        sprite_dir.symlink_to(moved_app, target_is_directory=True)
        return original_replace(src, dst, *args, **kwargs)

    def second_parent_swap(*args, **kwargs):
        nonlocal snapshot_calls
        snapshot_calls += 1
        if snapshot_calls == 3:
            sprite_dir.unlink()
            sprite_dir.symlink_to(decoy, target_is_directory=True)
        return original_snapshot(*args, **kwargs)

    monkeypatch.setattr(sprite_names_module, "os", NoDirFdOs())
    monkeypatch.setattr(
        sprite_names_module, "_supports_directory_fd_replace", lambda: False, raising=False
    )
    monkeypatch.setattr(
        sprite_names_module, "_is_windows_platform", lambda: False, raising=False
    )
    monkeypatch.setattr(real_os, "replace", first_parent_swap)
    monkeypatch.setattr(sprite_names_module, "_directory_snapshot", second_parent_swap)

    with pytest.raises(InvalidSpriteName):
        manager.feed_chunk(
            {
                "name": "Purple",
                "frame_index": 0,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"frame",
            }
        )

    assert replace_calls == 0
    assert manager.pending_count() == 0
    assert not (moved_app / "Fish-1.png").exists()


def test_windows_directory_guard_spans_replace_and_postcheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    original_replace = os.replace

    @contextmanager
    def guard(_directory: Path):
        events.append("guard-enter")

        def verify() -> None:
            events.append("guard-verify")

        try:
            yield verify
        finally:
            events.append("guard-exit")

    def observed_replace(src, dst, *args, **kwargs):
        events.append("replace")
        return original_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(
        sprite_names_module, "_supports_directory_fd_replace", lambda: False, raising=False
    )
    monkeypatch.setattr(
        sprite_names_module, "_is_windows_platform", lambda: True, raising=False
    )
    monkeypatch.setattr(
        sprite_names_module, "_open_windows_directory_guard", guard, raising=False
    )
    monkeypatch.setattr(os, "replace", observed_replace)

    destination = sprite_names_module.atomic_write_sprite_bytes(
        tmp_path, "Purple", "Fish-1.png", b"frame"
    )

    replace_index = events.index("replace")
    assert events.index("guard-enter") < replace_index < events.index("guard-exit")
    assert "guard-verify" in events[:replace_index]
    assert "guard-verify" in events[replace_index + 1 :]
    assert destination.read_bytes() == b"frame"


def test_windows_directory_guard_failure_prevents_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replace_calls = 0

    @contextmanager
    def failing_guard(_directory: Path):
        raise InvalidSpriteName("directory lock unavailable")
        yield

    def forbidden_replace(*_args, **_kwargs):
        nonlocal replace_calls
        replace_calls += 1

    monkeypatch.setattr(
        sprite_names_module, "_supports_directory_fd_replace", lambda: False, raising=False
    )
    monkeypatch.setattr(
        sprite_names_module, "_is_windows_platform", lambda: True, raising=False
    )
    monkeypatch.setattr(
        sprite_names_module, "_open_windows_directory_guard", failing_guard, raising=False
    )
    monkeypatch.setattr(os, "replace", forbidden_replace)

    with pytest.raises(InvalidSpriteName, match="lock unavailable"):
        sprite_names_module.atomic_write_sprite_bytes(
            tmp_path, "Purple", "Fish-1.png", b"frame"
        )

    assert replace_calls == 0
    assert not (tmp_path / "Purple" / "Fish-1.png").exists()


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


def test_legacy_migration_leaves_populated_canonical_tree_unchanged(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    canonical_frame = sprite_root / "Fish A" / "Fish-1.png"
    old_root.mkdir()
    canonical_frame.parent.mkdir(parents=True)
    (old_root / "FishA-2.png").write_bytes(b"legacy-frame")
    canonical_frame.write_bytes(b"canonical-frame")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)
    inventory_before = {
        path.relative_to(sprite_root): path.read_bytes()
        for path in sprite_root.rglob("*")
        if path.is_file()
    }

    manager._migrate_if_needed()

    inventory_after = {
        path.relative_to(sprite_root): path.read_bytes()
        for path in sprite_root.rglob("*")
        if path.is_file()
    }
    assert inventory_after == inventory_before
    assert not (sprite_root / "Free Fish Icons").exists()


def test_legacy_migration_populates_canonical_tree_when_it_has_no_frames(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    old_root.mkdir()
    sprite_root.mkdir()
    (old_root / "FishA-1.png").write_bytes(b"legacy-frame")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    manager._migrate_if_needed()

    assert (sprite_root / "Fish A" / "Fish-1.png").read_bytes() == b"legacy-frame"
    assert not (sprite_root / "Free Fish Icons").exists()


def test_legacy_migration_does_not_treat_custom_only_tree_as_complete(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    custom_frame = sprite_root / "Purple" / "Fish-1.png"
    old_root.mkdir()
    custom_frame.parent.mkdir(parents=True)
    (old_root / "FishA-1.png").write_bytes(b"legacy-a")
    (old_root / "FishB-1.png").write_bytes(b"legacy-b")
    custom_frame.write_bytes(b"custom")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    manager._migrate_if_needed()

    assert custom_frame.read_bytes() == b"custom"
    assert (sprite_root / "Fish A" / "Fish-1.png").read_bytes() == b"legacy-a"
    assert (sprite_root / "Fish B" / "Fish-1.png").read_bytes() == b"legacy-b"


def test_legacy_migration_fills_partial_targets_without_overwrite_and_is_idempotent(
    tmp_path: Path,
) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    existing_frame = sprite_root / "Fish A" / "Fish-1.png"
    old_root.mkdir()
    existing_frame.parent.mkdir(parents=True)
    (old_root / "FishA-1.png").write_bytes(b"legacy-a1")
    (old_root / "FishA-2.png").write_bytes(b"legacy-a2")
    (old_root / "FishB-1.png").write_bytes(b"legacy-b1")
    existing_frame.write_bytes(b"canonical-a1")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    manager._migrate_if_needed()

    assert existing_frame.read_bytes() == b"canonical-a1"
    assert (sprite_root / "Fish A" / "Fish-2.png").read_bytes() == b"legacy-a2"
    assert (sprite_root / "Fish B" / "Fish-1.png").read_bytes() == b"legacy-b1"
    inventory_after_first_call = {
        path.relative_to(sprite_root): path.read_bytes()
        for path in sprite_root.rglob("*")
        if path.is_file()
    }

    manager._migrate_if_needed()

    inventory_after_second_call = {
        path.relative_to(sprite_root): path.read_bytes()
        for path in sprite_root.rglob("*")
        if path.is_file()
    }
    assert inventory_after_second_call == inventory_after_first_call


def test_legacy_migration_does_not_trust_empty_sentinel(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    old_root.mkdir()
    (sprite_root / "Free Fish Icons").mkdir(parents=True)
    (old_root / "FishA-1.png").write_bytes(b"legacy-a")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    manager._migrate_if_needed()

    assert (sprite_root / "Fish A" / "Fish-1.png").read_bytes() == b"legacy-a"


def test_legacy_migration_rejects_symlink_sprite_root(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    outside = tmp_path / "outside"
    sprite_root = tmp_path / "fish_sprites"
    old_root.mkdir()
    outside.mkdir()
    sprite_root.symlink_to(outside, target_is_directory=True)
    (old_root / "FishA-1.png").write_bytes(b"legacy-a")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    with pytest.raises(InvalidSpriteName):
        manager._migrate_if_needed()

    assert list(outside.iterdir()) == []


def test_legacy_migration_rejects_symlink_target_type(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    outside = tmp_path / "outside"
    old_root.mkdir()
    sprite_root.mkdir()
    outside.mkdir()
    (old_root / "FishA-1.png").write_bytes(b"legacy-a")
    (sprite_root / "Fish A").symlink_to(outside, target_is_directory=True)
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    with pytest.raises(InvalidSpriteName):
        manager._migrate_if_needed()

    assert list(outside.iterdir()) == []


def test_directory_validation_rejects_windows_reparse_attribute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "sprites"
    directory.mkdir()
    original_lstat = Path.lstat

    class ReparseMetadata:
        st_mode = directory.stat().st_mode
        st_file_attributes = 0x00000400

    def reparse_lstat(path: Path):
        if path == directory:
            return ReparseMetadata()
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", reparse_lstat)

    with pytest.raises(InvalidSpriteName, match="reparse"):
        sprite_names_module.ensure_safe_directory(directory)


def test_legacy_migration_skips_source_symlink(tmp_path: Path) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    outside = tmp_path / "outside.png"
    old_root.mkdir()
    sprite_root.mkdir()
    outside.write_bytes(b"outside-secret")
    (old_root / "FishA-1.png").symlink_to(outside)
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)

    manager._migrate_if_needed()

    assert not (sprite_root / "Fish A" / "Fish-1.png").exists()
    assert outside.read_bytes() == b"outside-secret"


def test_legacy_migration_fails_closed_when_source_changes_while_opening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_root = tmp_path / "Free Fish Icons"
    sprite_root = tmp_path / "fish_sprites"
    source = old_root / "FishA-1.png"
    moved_source = old_root / "original.png"
    outside = tmp_path / "outside.png"
    old_root.mkdir()
    sprite_root.mkdir()
    source.write_bytes(b"legacy-a")
    outside.write_bytes(b"outside-secret")
    manager = SpriteManager.__new__(SpriteManager)
    manager.OLD_DIR = str(old_root)
    manager.SPRITE_DIR = str(sprite_root)
    original_open = Path.open
    attacked = False

    def swap_before_open(path: Path, *args, **kwargs):
        nonlocal attacked
        if path == source and not attacked:
            source.rename(moved_source)
            source.symlink_to(outside)
            attacked = True
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", swap_before_open)

    manager._migrate_if_needed()

    assert attacked is True
    assert not (sprite_root / "Fish A" / "Fish-1.png").exists()
    assert outside.read_bytes() == b"outside-secret"


def test_atomic_create_if_missing_never_overwrites_existing_frame(tmp_path: Path) -> None:
    destination = tmp_path / "Purple" / "Fish-1.png"
    destination.parent.mkdir()
    destination.write_bytes(b"canonical")

    created = sprite_names_module.atomic_write_sprite_bytes_if_missing(
        tmp_path,
        "Purple",
        "Fish-1.png",
        b"legacy",
    )

    assert created is False
    assert destination.read_bytes() == b"canonical"


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


def test_ui_import_callback_turns_invalid_name_into_failed_import(caplog) -> None:
    class SpriteManagerDouble:
        def import_sprites(self, _source: str, _name: str) -> bool:
            raise InvalidSpriteName("unsafe")

    class PanelDouble:
        def refresh_fish_types(self) -> None:
            raise AssertionError("failed import must not refresh UI state")

        def set_bg_type(self, _bg_type: str) -> None:
            raise AssertionError("failed import must not refresh UI state")

    background = type("BackgroundDouble", (), {"bg_type": "gradient"})()

    app_logger = logging.getLogger("fish_demo.app")
    original_propagate = app_logger.propagate
    app_logger.addHandler(caplog.handler)
    app_logger.propagate = False
    try:
        assert main._handle_sprite_import(
            SpriteManagerDouble(), PanelDouble(), background, "CON", "/tmp/source"
        ) is False
    finally:
        app_logger.removeHandler(caplog.handler)
        app_logger.propagate = original_propagate
    record = caplog.records[-1]
    assert record.event == "sprite_import_rejected"
    assert record.sprite_name == "CON"
    assert record.error == "unsafe"
