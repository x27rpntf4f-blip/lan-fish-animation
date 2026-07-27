from __future__ import annotations

import json
import logging
from pathlib import Path

import fishmesh.logging as mesh_logging
from fish_demo import app
from fish_demo.cli import parse_args
from fish_demo.network_handlers import handle_network_message
from fishmesh.logging import EventRateLimiter, configure_logging, log_rate_limited_event
from network import NetworkManager
from sprite_manager import SpriteManager
from sprite_sync import SpriteSyncManager


def _remove_configured_handlers(original_handlers: list[logging.Handler]) -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if handler not in original_handlers:
            root.removeHandler(handler)
            handler.close()
    configured_handlers = set()
    for name in ("fishmesh", "fish_demo", "network", "sprite_manager", "sprite_sync"):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            if handler.__class__.__name__ == "_FishMeshHandler":
                logger.removeHandler(handler)
                configured_handlers.add(handler)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    for handler in configured_handlers:
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


def test_rate_limiter_suppresses_repeated_event_for_same_peer(caplog) -> None:
    limiter = EventRateLimiter(window_seconds=10, clock=lambda: 100.0)
    logger = logging.getLogger("fishmesh.test.rate.same")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        for _ in range(5):
            log_rate_limited_event(
                logger,
                logging.WARNING,
                "send failed",
                event="packet_send_failed",
                stable_key="192.0.2.1:6000",
                extra={"peer": "192.0.2.1:6000", "error": "offline"},
                limiter=limiter,
            )

    assert [record.event for record in caplog.records] == ["packet_send_failed"]
    assert not hasattr(caplog.records[0], "suppressed_count")


def test_rate_limiter_tracks_peers_independently(caplog) -> None:
    limiter = EventRateLimiter(window_seconds=10, clock=lambda: 100.0)
    logger = logging.getLogger("fishmesh.test.rate.peers")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        for peer in ("192.0.2.1:6000", "192.0.2.2:6000"):
            log_rate_limited_event(
                logger,
                logging.WARNING,
                "send failed",
                event="packet_send_failed",
                stable_key=peer,
                extra={"peer": peer, "error": "offline"},
                limiter=limiter,
            )

    assert [record.peer for record in caplog.records] == [
        "192.0.2.1:6000",
        "192.0.2.2:6000",
    ]


def test_rate_limiter_reports_suppressed_count_after_window(caplog) -> None:
    now = [100.0]
    limiter = EventRateLimiter(window_seconds=10, clock=lambda: now[0])
    logger = logging.getLogger("fishmesh.test.rate.window")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        for _ in range(5):
            log_rate_limited_event(
                logger,
                logging.WARNING,
                "packet discarded",
                event="packet_discarded",
                stable_key="192.0.2.1:6000",
                extra={"peer": "192.0.2.1:6000", "error": "bad packet"},
                limiter=limiter,
            )
        now[0] = 110.0
        log_rate_limited_event(
            logger,
            logging.WARNING,
            "packet discarded",
            event="packet_discarded",
            stable_key="192.0.2.1:6000",
            extra={"peer": "192.0.2.1:6000", "error": "bad packet"},
            limiter=limiter,
        )

    assert len(caplog.records) == 2
    assert caplog.records[-1].suppressed_count == 4


def test_malformed_packet_warning_uses_runtime_rate_limiter(monkeypatch, caplog) -> None:
    limiter = EventRateLimiter(window_seconds=10, clock=lambda: 100.0)
    monkeypatch.setattr(mesh_logging, "_NETWORK_EVENT_LIMITER", limiter, raising=False)

    with caplog.at_level(logging.WARNING):
        for _ in range(5):
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

    records = [record for record in caplog.records if record.event == "packet_discarded"]
    assert len(records) == 1


def test_packet_send_warning_uses_runtime_rate_limiter(monkeypatch, caplog) -> None:
    class FailingSocket:
        def sendto(self, _data, _address) -> None:
            raise OSError("offline")

    limiter = EventRateLimiter(window_seconds=10, clock=lambda: 100.0)
    monkeypatch.setattr(mesh_logging, "_NETWORK_EVENT_LIMITER", limiter, raising=False)
    manager = NetworkManager.__new__(NetworkManager)
    manager.sock = FailingSocket()

    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            manager.send("192.0.2.20", 6200, b"packet")

    records = [record for record in caplog.records if record.event == "packet_send_failed"]
    assert len(records) == 1


def test_json_logging_normalizes_pathological_values(capsys) -> None:
    circular = []
    circular.append(circular)
    deep = "bottom"
    for _ in range(20):
        deep = [deep]

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("WARNING", json_output=True)
        logging.getLogger("fishmesh.test.json.pathological").warning(
            "pathological payload",
            extra={
                "event": "pathological_event",
                "payload": {
                    ("tuple", 1): {"set": {3, 2, 1}, "tuple": ("a", "b")},
                    "numbers": [float("nan"), float("inf"), float("-inf")],
                    "error": OSError("offline"),
                    "cycle": circular,
                    "deep": deep,
                },
            },
        )

        lines = capsys.readouterr().err.splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["event"] == "pathological_event"
        assert payload["payload"]["numbers"] == ["NaN", "Infinity", "-Infinity"]
        assert payload["payload"]["cycle"] == ["<cycle>"]
        assert payload["payload"]["('tuple', 1)"]["set"] == [1, 2, 3]
        assert payload["payload"]["('tuple', 1)"]["tuple"] == ["a", "b"]
        assert payload["payload"]["error"] == "offline"
        assert "<max_depth>" in lines[0]
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_json_logging_falls_back_when_message_stringification_fails(capsys) -> None:
    class BadString:
        def __str__(self) -> str:
            raise RuntimeError("cannot stringify")

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("WARNING", json_output=True)
        logging.getLogger("fishmesh.test.json.fallback").warning(
            "bad value: %s",
            BadString(),
            extra={"event": "formatting_failed_but_preserved"},
        )

        lines = capsys.readouterr().err.splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["event"] == "formatting_failed_but_preserved"
        assert payload["message"] == "<message formatting failed>"
        assert payload["format_error"] == "RuntimeError: cannot stringify"
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_configuration_leaves_root_logging_untouched() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("ERROR")
        configure_logging("DEBUG", json_output=True)

        assert root.handlers == original_handlers
        assert root.level == original_level
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_configuration_excludes_third_party_logs_from_fishmesh_stream(capsys) -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging("WARNING")
        logging.getLogger("third.party").warning(
            "external warning",
            extra={"event": "third_party_event"},
        )
        logging.getLogger("fishmesh.runtime").warning(
            "runtime warning",
            extra={"event": "project_event"},
        )

        lines = capsys.readouterr().err.splitlines()
        assert len(lines) == 1
        assert "project_event" in lines[0]
        assert "third_party_event" not in lines[0]
    finally:
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_reconfiguration_preserves_user_handler_without_duplicate_project_output(capsys) -> None:
    class UserHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.records = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record)

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    project_logger = logging.getLogger("fishmesh")
    user_handler = UserHandler()
    project_logger.addHandler(user_handler)
    try:
        configure_logging("INFO")
        configure_logging("INFO", json_output=True)
        logging.getLogger("fishmesh.runtime").info(
            "runtime ready",
            extra={"event": "runtime_ready"},
        )

        lines = capsys.readouterr().err.splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "runtime_ready"
        assert project_logger.handlers.count(user_handler) == 1
        assert len(user_handler.records) == 1
    finally:
        project_logger.removeHandler(user_handler)
        _remove_configured_handlers(original_handlers)
        root.setLevel(original_level)


def test_info_and_warning_sprite_events_do_not_expose_absolute_paths(tmp_path, caplog) -> None:
    manager = SpriteManager.__new__(SpriteManager)
    manager.SPRITE_DIR = str(tmp_path / "installed" / "fish_sprites")
    missing_source = str(tmp_path / "users" / "private" / "missing")

    with caplog.at_level(logging.INFO):
        manager._scan_sprites_dir()
        manager._scan_sprites_dir()
        assert manager.import_sprites(missing_source, "Koi") is False

    for record in caplog.records:
        if record.levelno >= logging.INFO:
            assert str(tmp_path) not in " ".join(
                value for value in record.__dict__.values() if isinstance(value, str)
            )
