import configparser
import os

DEFAULTS = {
    "Display": {"width": "800", "height": "600", "fullscreen": "false"},
    "Fish": {"count": "5", "speed_multiplier": "1.0"},
    "Network": {"port": "6000", "heartbeat_interval": "3", "heartbeat_timeout": "10"},
    "Audio": {"enabled": "true", "volume": "0.5"},
    "Background": {"type": "gradient", "path": ""},
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")


def load():
    cfg = configparser.ConfigParser()
    for section, items in DEFAULTS.items():
        cfg[section] = items
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH)
    return cfg


def save(cfg):
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)
