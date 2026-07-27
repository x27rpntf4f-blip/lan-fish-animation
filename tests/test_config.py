from __future__ import annotations

import configparser
from pathlib import Path

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
