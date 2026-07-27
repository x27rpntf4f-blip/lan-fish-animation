import configparser
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
    """Return the user-writable configuration path for the current invocation."""
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
    """Persist configuration as UTF-8 without assuming an install location is writable."""
    config_path = Path(path) if path is not None else _default_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        cfg.write(f)
