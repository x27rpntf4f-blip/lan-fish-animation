from __future__ import annotations

import os
import stat
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path


class InvalidSpriteName(ValueError):
    """Raised when a sprite name cannot safely identify one local directory."""


_WINDOWS_FORBIDDEN = frozenset('<>:"|?*')
_WINDOWS_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL"}) | frozenset(
    {f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)}
)


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
    if any(char in _WINDOWS_FORBIDDEN for char in name):
        raise InvalidSpriteName("sprite name contains a character forbidden on Windows")
    if name.endswith((".", " ")):
        raise InvalidSpriteName("sprite name cannot end with a dot or space")
    device_stem = name.partition(".")[0].rstrip(" .").upper()
    if device_stem in _WINDOWS_RESERVED:
        raise InvalidSpriteName("sprite name cannot use a reserved Windows device name")
    if len(name.encode("utf-8")) > 255:
        raise InvalidSpriteName("sprite name must fit in 255 UTF-8 bytes")
    return name


def resolve_sprite_directory(sprite_root: str | Path, value: str) -> tuple[str, Path]:
    """Resolve a validated sprite name to a direct child of ``sprite_root``."""
    name = validate_sprite_name(value)
    root = Path(sprite_root).resolve()
    destination = (root / name).resolve()
    if destination.parent != root:
        raise InvalidSpriteName("sprite destination must be a direct child of the sprite root")
    return name, destination


def _validate_file_component(filename: str) -> None:
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise InvalidSpriteName("sprite filename must be one path component")


def _validate_replace_target(destination: Path) -> None:
    try:
        mode = destination.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode) or stat.S_ISREG(mode):
        return
    raise InvalidSpriteName("sprite frame destination must be a regular file or replaceable link")


def atomic_replace_sprite_file(
    sprite_root: str | Path,
    sprite_name: str,
    filename: str,
    writer: Callable[[Path], None],
) -> Path:
    """Write beside the destination, sync it, then replace the directory entry."""
    _validate_file_component(filename)
    sprite_name, destination_dir = resolve_sprite_directory(sprite_root, sprite_name)
    destination_dir.mkdir(parents=True, exist_ok=True)
    sprite_name, destination_dir = resolve_sprite_directory(sprite_root, sprite_name)
    destination = destination_dir / filename
    _validate_replace_target(destination)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination_dir,
        prefix=f".{filename}.",
        suffix=".png",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        writer(temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        _, current_dir = resolve_sprite_directory(sprite_root, sprite_name)
        if current_dir != destination_dir:
            raise InvalidSpriteName("sprite directory changed during write")
        _validate_replace_target(destination)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def atomic_write_sprite_bytes(
    sprite_root: str | Path,
    sprite_name: str,
    filename: str,
    data: bytes,
) -> Path:
    """Atomically replace one sprite frame with in-memory bytes."""

    def _write(temporary: Path) -> None:
        temporary.write_bytes(data)

    return atomic_replace_sprite_file(
        sprite_root,
        sprite_name,
        filename,
        _write,
    )


def read_regular_sprite_file(
    sprite_root: str | Path,
    sprite_name: str,
    filename: str,
) -> bytes:
    """Read one in-root regular file without following a frame symlink."""
    _validate_file_component(filename)
    _, directory = resolve_sprite_directory(sprite_root, sprite_name)
    path = directory / filename
    try:
        initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise InvalidSpriteName("sprite frame must be a regular file")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            current = path.lstat()
            if not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(current.st_mode):
                raise InvalidSpriteName("sprite frame must be a regular file")
            identities = {
                (initial.st_dev, initial.st_ino),
                (opened.st_dev, opened.st_ino),
                (current.st_dev, current.st_ino),
            }
            if len(identities) != 1:
                raise InvalidSpriteName("sprite frame changed while opening")
            if path.resolve().parent != directory:
                raise InvalidSpriteName("sprite frame must remain inside its sprite directory")
            return stream.read()
    except FileNotFoundError as exc:
        raise InvalidSpriteName("sprite frame disappeared while opening") from exc
