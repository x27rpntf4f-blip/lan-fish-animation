from __future__ import annotations

import json
import logging
from pathlib import Path

from fish_demo import app
from fish_demo.cli import parse_args
from fish_demo.network_handlers import handle_network_message
from fishmesh.logging import configure_logging
from sprite_sync import SpriteSyncManager


def _remove_configured_handlers(original_handlers: list[logging.Handler]) -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if handler not in original_handlers:
            root.removeHandler(handler)
            handler.close()


def test_malformed_packet_records_structured_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        handle_network_message(
            b"\x00",
            ("192.0.2.10", 6200),
            object(),
            object(),
            [],
            800,
            600,
            object(),
            object(),
        )

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert record.event == "packet_discarded"
    assert record.peer == "192.0.2.10:6200"
    assert isinstance(record.error, str)


def test_completed_sprite_frame_records_structured_event(tmp_path: Path, caplog) -> None:
    manager = SpriteSyncManager(tmp_path)

    with caplog.at_level(logging.INFO):
        complete = manager.feed_chunk(
            {
                "name": "Blue Fish",
                "frame_index": 2,
                "total_chunks": 1,
                "chunk_index": 0,
                "data": b"png bytes",
            }
        )

    assert complete is True
    record = caplog.records[-1]
    assert record.event == "sprite_frame_saved"
    assert record.sprite_name == "Blue Fish"
    assert record.frame_index == 2


def test_repeated_configuration_emits_each_text_event_once(capsys) -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("INFO", json_output=False)
        configure_logging("INFO", json_output=False)

        logging.getLogger("fishmesh.test.text").info(
            "frame ready",
            extra={"event": "frame_ready", "sprite_name": "Koi"},
        )

        lines = [line for line in capsys.readouterr().err.splitlines() if "frame_ready" in line]
        assert len(lines) == 1
        assert "sprite_name=Koi" in lines[0]
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_json_logging_emits_one_serializable_object_per_line(capsys) -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("WARNING", json_output=True)
        logging.getLogger("fishmesh.test.json").warning(
            "send failed",
            extra={
                "event": "packet_send_failed",
                "error": OSError("offline"),
                "logger": "spoofed.logger",
            },
        )

        lines = capsys.readouterr().err.splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["level"] == "WARNING"
        assert payload["logger"] == "fishmesh.test.json"
        assert payload["event"] == "packet_send_failed"
        assert payload["error"] == "offline"
        assert payload["message"] == "send failed"
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_cli_accepts_only_supported_log_levels() -> None:
    assert parse_args(["--log-level", "DEBUG"]).log_level == "DEBUG"


def test_main_configures_logging_before_loading_runtime(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(app, "configure_logging", lambda level: calls.append(("log", level)))
    monkeypatch.setattr(app, "load", lambda: calls.append(("load", None)) or {})
    monkeypatch.setattr(app, "_main", lambda args, cfg, resources: calls.append(("run", None)))

    assert app.main(["--log-level", "ERROR"]) == 0
    assert calls == [("log", "ERROR"), ("load", None), ("run", None)]
