from __future__ import annotations

import unicodedata
from pathlib import Path


class InvalidSpriteName(ValueError):
    """Raised when a sprite name cannot safely identify one local directory."""


def validate_sprite_name(value: str) -> str:
    """Return the canonical sprite name or reject unsafe resource identifiers."""
    if not isinstance(value, str):
        raise InvalidSpriteName("sprite name must be text")

    name = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(name) <= 64:
        raise InvalidSpriteName("sprite name must contain 1 to 64 characters")
    if name in {".", ".."}:
        raise InvalidSpriteName("sprite name cannot be a relative path component")
    if "/" in name or "\\" in name:
        raise InvalidSpriteName("sprite name cannot contain a path separator")
    if any(unicodedata.category(char) == "Cc" for char in name):
        raise InvalidSpriteName("sprite name cannot contain control characters")
    return name


def resolve_sprite_directory(sprite_root: str | Path, value: str) -> tuple[str, Path]:
    """Resolve a validated sprite name to a direct child of ``sprite_root``."""
    name = validate_sprite_name(value)
    root = Path(sprite_root).resolve()
    destination = (root / name).resolve()
    if destination.parent != root:
        raise InvalidSpriteName("sprite destination must be a direct child of the sprite root")
    return name, destination
