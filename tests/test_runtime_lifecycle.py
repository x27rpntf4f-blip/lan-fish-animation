from __future__ import annotations

import configparser
from types import SimpleNamespace

import pytest

import main


class _Screen:
    def get_width(self) -> int:
        return 800

    def get_height(self) -> int:
        return 600


class _Pygame:
    DOUBLEBUF = 1
    FULLSCREEN = 2

    def __init__(self) -> None:
        self.quit_called = False
        self.display = SimpleNamespace(
            set_mode=lambda *_args: _Screen(),
            set_caption=lambda *_args: None,
            get_init=lambda: not self.quit_called,
        )
        self.mixer = SimpleNamespace(get_init=lambda: not self.quit_called)
        self.time = SimpleNamespace(Clock=lambda: SimpleNamespace())

    def init(self) -> None:
        pass

    def quit(self) -> None:
        self.quit_called = True


class _FailingPygame(_Pygame):
    def init(self) -> None:
        raise RuntimeError("pygame initialization failed")


class _Audio:
    def __init__(self, **_kwargs: object) -> None:
        self.stopped = False

    def play(self) -> None:
        pass

    def stop(self) -> None:
        self.stopped = True


class _Background:
    def __init__(self, *_args: object) -> None:
        self.cleaned = False
        self.bg_type = "gradient"

    def cleanup(self) -> None:
        self.cleaned = True


class _SpriteManager:
    SPRITE_DIR = "unused"

    def get_types(self) -> list[str]:
        return []


class _Panel:
    def __init__(self, *_args: object) -> None:
        pass

    def set_bg_type(self, *_args: object) -> None:
        pass

    def set_sprite_manager(self, *_args: object) -> None:
        pass

    def set_on_import(self, *_args: object) -> None:
        pass


class _Registry:
    def __init__(self, port: int) -> None:
        self.my_hostname = "test-host"
        self.my_ip = "127.0.0.1"
        self.my_id = 0
        self.port = port


class _Network:
    def __init__(self, _port: int) -> None:
        self.port = 6200
        self.shutdown_called = False

    def start_listen(self, _queue: object) -> None:
        pass

    def broadcast(self, _packet: bytes) -> None:
        raise RuntimeError("discovery failed")

    def shutdown(self) -> None:
        self.shutdown_called = True


def _unexpected_input(_prompt: str) -> str:
    raise AssertionError("input() was called")


def _config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "Display": {"width": "800", "height": "600", "fullscreen": "true"},
            "Fish": {"count": "1", "speed_multiplier": "1.0"},
            "Network": {"port": "6200", "heartbeat_interval": "3", "heartbeat_timeout": "10"},
            "Audio": {"enabled": "true", "volume": "0.5"},
            "Background": {"type": "gradient", "path": ""},
        }
    )
    return cfg


def _install_runtime_fakes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_Pygame, _Audio, _Background, _Network]:
    pygame = _Pygame()
    audio = _Audio()
    background = _Background()
    network = _Network(6200)
    monkeypatch.setattr(main, "pygame", pygame)
    monkeypatch.setattr(main, "AudioManager", lambda **_kwargs: audio)
    monkeypatch.setattr(main, "BackgroundManager", lambda *_args: background)
    monkeypatch.setattr(main, "SpriteManager", _SpriteManager)
    monkeypatch.setattr(main, "SpriteSyncManager", lambda *_args: object())
    monkeypatch.setattr(main, "RequestTracker", lambda **_kwargs: object())
    monkeypatch.setattr(main, "ConfigPanel", _Panel)
    monkeypatch.setattr(main, "NetworkManager", lambda _port: network)
    monkeypatch.setattr(main, "HostRegistry", _Registry)
    monkeypatch.setattr(main.msg, "pack_hello", lambda *_args: b"hello")
    return pygame, audio, background, network


def test_startup_overrides_are_separate_from_later_ui_saves() -> None:
    """Would fail if diagnostic startup flags mutate the config later saved by UI actions."""
    cfg = _config()
    args = SimpleNamespace(windowed=True, no_audio=True)

    fullscreen_start, audio_enabled = main.startup_options(cfg, args)
    cfg["Fish"]["count"] = "2"  # representative later UI edit before save(cfg)

    assert fullscreen_start is False
    assert audio_enabled is False
    assert cfg["Display"]["fullscreen"] == "true"
    assert cfg["Audio"]["enabled"] == "true"


def test_interactive_save_keeps_diagnostic_overrides_out_of_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Would fail if windowed or no-audio changes the configuration passed to save()."""
    cfg = _config()
    saved_snapshots: list[tuple[str, str]] = []
    _install_runtime_fakes(monkeypatch)
    monkeypatch.setattr(main, "load", lambda: cfg)
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda: SimpleNamespace(
            port=6200,
            expected_hosts=None,
            run_seconds=0.0,
            windowed=True,
            no_audio=True,
        ),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    monkeypatch.setattr(
        main,
        "save",
        lambda value: saved_snapshots.append(
            (value["Display"]["fullscreen"], value["Audio"]["enabled"])
        ),
    )

    with pytest.raises(RuntimeError, match="discovery failed"):
        main.main()

    assert saved_snapshots == [("true", "true")]


def test_pygame_initialization_exception_still_quits_pygame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Would fail if a partially initialized Pygame runtime is not released."""
    pygame = _FailingPygame()
    monkeypatch.setattr(main, "pygame", pygame)
    monkeypatch.setattr(main, "load", _config)
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda: SimpleNamespace(
            port=6200,
            expected_hosts=1,
            run_seconds=0.0,
            windowed=False,
            no_audio=False,
        ),
    )

    with pytest.raises(RuntimeError, match="pygame initialization failed"):
        main.main()

    assert pygame.quit_called is True


def test_discovery_exception_cleans_every_created_runtime_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Would fail if a discovery exception bypasses shutdown of initialized resources."""
    cfg = _config()
    pygame, audio, background, network = _install_runtime_fakes(monkeypatch)
    monkeypatch.setattr(main, "load", lambda: cfg)
    monkeypatch.setattr(
        main,
        "parse_args",
        lambda: SimpleNamespace(
            port=6200,
            expected_hosts=1,
            run_seconds=0.0,
            windowed=True,
            no_audio=True,
        ),
    )
    monkeypatch.setattr("builtins.input", _unexpected_input)

    with pytest.raises(RuntimeError, match="discovery failed"):
        main.main()

    assert network.shutdown_called is True
    assert background.cleaned is True
    assert audio.stopped is True
    assert pygame.quit_called is True
    assert pygame.display.get_init() is False
    assert pygame.mixer.get_init() is False
