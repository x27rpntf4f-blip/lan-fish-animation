from __future__ import annotations

import configparser
import os
from pathlib import Path

import pytest

from config import load, save


def test_load_uses_complete_portable_defaults_when_file_is_missing(tmp_path: Path) -> None:
    cfg = load(tmp_path / "missing.ini")

    assert cfg["Display"] == {"width": "800", "height": "600", "fullscreen": "false"}
    assert cfg["Fish"] == {"count": "5", "speed_multiplier": "1.0"}
    assert cfg["Network"]["expected_hosts"] == "2"
    assert cfg["Audio"]["enabled"] == "true"
    assert cfg["Background"] == {"type": "gradient", "path": ""}


def test_save_creates_parent_directories_and_round_trips_unicode_as_utf8(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.ini"
    cfg = load(path)
    cfg["Background"]["path"] = "素材/海底.png"

    save(cfg, path)

    assert path.read_text(encoding="utf-8").find("素材/海底.png") >= 0
    assert load(path)["Background"]["path"] == "素材/海底.png"
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_save_preserves_previous_bytes_when_write_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.ini"
    previous = b"previous configuration\n\xff"
    path.write_bytes(previous)
    cfg = load(tmp_path / "new.ini")

    def fail_write(_file: object) -> None:
        raise OSError("write failed")

    monkeypatch.setattr(cfg, "write", fail_write)

    with pytest.raises(OSError, match="write failed"):
        save(cfg, path)

    assert path.read_bytes() == previous
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_save_preserves_previous_bytes_when_fsync_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.ini"
    previous = b"previous configuration\n"
    path.write_bytes(previous)
    cfg = load(tmp_path / "new.ini")

    def fail_fsync(_file_descriptor: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="fsync failed"):
        save(cfg, path)

    assert path.read_bytes() == previous
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_save_preserves_previous_bytes_when_flush_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.ini"
    previous = b"previous configuration\n"
    path.write_bytes(previous)
    cfg = load(tmp_path / "new.ini")
    original_fdopen = os.fdopen

    class FlushFailingFile:
        def __init__(self, file: object) -> None:
            self.file = file

        def __enter__(self) -> object:
            self.file.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self.file.__exit__(*args)

        def write(self, value: str) -> object:
            return self.file.write(value)

        def flush(self) -> None:
            raise OSError("flush failed")

        def fileno(self) -> int:
            return self.file.fileno()

    def fail_flush(*args: object, **kwargs: object) -> FlushFailingFile:
        return FlushFailingFile(original_fdopen(*args, **kwargs))

    monkeypatch.setattr(os, "fdopen", fail_flush)

    with pytest.raises(OSError, match="flush failed"):
        save(cfg, path)

    assert path.read_bytes() == previous
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_save_preserves_previous_bytes_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "config.ini"
    previous = b"previous configuration\n"
    path.write_bytes(previous)
    cfg = load(tmp_path / "new.ini")

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        save(cfg, path)

    assert path.read_bytes() == previous
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_default_path_is_config_ini_in_the_current_working_directory(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load()
    cfg["Fish"]["count"] = "7"

    save(cfg)

    assert load()["Fish"]["count"] == "7"
    assert (tmp_path / "config.ini").is_file()


def test_tracked_configuration_templates_match_portable_defaults() -> None:
    project_root = Path(__file__).resolve().parents[1]
    tracked = project_root / "config.ini"
    example = project_root / "config.example.ini"

    assert tracked.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")

    cfg = configparser.ConfigParser()
    cfg.read(tracked, encoding="utf-8")
    assert cfg["Display"] == {"width": "800", "height": "600", "fullscreen": "false"}
    assert cfg["Fish"] == {"count": "5", "speed_multiplier": "1.0"}
    assert cfg["Network"]["expected_hosts"] == "2"
    assert cfg["Audio"]["enabled"] == "true"
    assert cfg["Background"] == {"type": "gradient", "path": ""}
