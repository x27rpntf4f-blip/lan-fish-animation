import configparser
import os
import tempfile
from pathlib import Path

DEFAULTS = {
    "Display": {"width": "800", "height": "600", "fullscreen": "false"},
    "Fish": {"count": "5", "speed_multiplier": "1.0"},
    "Network": {
        "port": "6000",
        "heartbeat_interval": "3",
        "heartbeat_timeout": "10",
        "expected_hosts": "2",
    },
    "Audio": {"enabled": "true", "volume": "0.5"},
    "Background": {"type": "gradient", "path": ""},
}

def _default_path() -> Path:
    """Return the default configuration path relative to the active working directory."""
    return Path.cwd() / "config.ini"


def load(path: Path | None = None) -> configparser.ConfigParser:
    """Load configuration from *path*, falling back to portable defaults."""
    config_path = Path(path) if path is not None else _default_path()
    cfg = configparser.ConfigParser()
    for section, items in DEFAULTS.items():
        cfg[section] = items
    if config_path.is_file():
        cfg.read(config_path, encoding="utf-8")
    return cfg


def save(cfg: configparser.ConfigParser, path: Path | None = None) -> None:
    """Atomically persist configuration as UTF-8 at an explicit or default path."""
    config_path = Path(path) if path is not None else _default_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=f".{config_path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)

    try:
        temporary_file = os.fdopen(file_descriptor, "w", encoding="utf-8")
        file_descriptor = -1
        with temporary_file:
            cfg.write(temporary_file)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, config_path)
    except BaseException:
        if file_descriptor != -1:
            os.close(file_descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise
