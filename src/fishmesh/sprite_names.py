from __future__ import annotations

import os
import stat
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO


class InvalidSpriteName(ValueError):
    """Raised when a sprite name cannot safely identify one local directory."""


_WINDOWS_FORBIDDEN = frozenset('<>:"|?*')
_WINDOWS_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}) | frozenset(
    {
        f"{prefix}{suffix}"
        for prefix in ("COM", "LPT")
        for suffix in (*map(str, range(1, 10)), "¹", "²", "³")
    }
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


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _directory_snapshot(
    sprite_root: str | Path,
    sprite_name: str,
) -> tuple[str, Path, Path, tuple[int, int], tuple[int, int]]:
    name, destination_dir = resolve_sprite_directory(sprite_root, sprite_name)
    root = Path(sprite_root).resolve()
    try:
        root_metadata = root.stat()
        directory_metadata = destination_dir.stat()
    except FileNotFoundError as exc:
        raise InvalidSpriteName("sprite directory disappeared during write") from exc
    if not stat.S_ISDIR(root_metadata.st_mode) or not stat.S_ISDIR(directory_metadata.st_mode):
        raise InvalidSpriteName("sprite root and destination must be directories")
    return name, root, destination_dir, _identity(root_metadata), _identity(directory_metadata)


def _entry_metadata(directory: Path, directory_fd: int | None, filename: str) -> os.stat_result:
    if directory_fd is not None:
        return os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
    return (directory / filename).lstat()


def _safe_unlink_entry(
    directory: Path,
    directory_fd: int | None,
    filename: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        metadata = _entry_metadata(directory, directory_fd, filename)
    except FileNotFoundError:
        return
    if not stat.S_ISLNK(metadata.st_mode) and _identity(metadata) != expected_identity:
        return
    if directory_fd is not None:
        os.unlink(filename, dir_fd=directory_fd)
    else:
        (directory / filename).unlink()


def _assert_directory_snapshot(
    sprite_root: str | Path,
    sprite_name: str,
    expected_root: Path,
    expected_directory: Path,
    expected_root_identity: tuple[int, int],
    expected_directory_identity: tuple[int, int],
) -> None:
    _, root, directory, root_identity, directory_identity = _directory_snapshot(
        sprite_root, sprite_name
    )
    if (
        root != expected_root
        or directory != expected_directory
        or root_identity != expected_root_identity
        or directory_identity != expected_directory_identity
    ):
        raise InvalidSpriteName("sprite directory changed during write")


def atomic_replace_sprite_file(
    sprite_root: str | Path,
    sprite_name: str,
    filename: str,
    writer: Callable[[BinaryIO], None],
) -> Path:
    """Write beside the destination, sync it, then replace the directory entry."""
    _validate_file_component(filename)
    sprite_name, destination_dir = resolve_sprite_directory(sprite_root, sprite_name)
    destination_dir.mkdir(parents=True, exist_ok=True)
    (
        sprite_name,
        root,
        destination_dir,
        root_identity,
        directory_identity,
    ) = _directory_snapshot(sprite_root, sprite_name)
    destination = destination_dir / filename
    _validate_replace_target(destination)

    directory_fd: int | None = None
    if os.name == "posix":
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(destination_dir, directory_flags)
        if _identity(os.fstat(directory_fd)) != directory_identity:
            os.close(directory_fd)
            raise InvalidSpriteName("sprite directory changed while opening")

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination_dir,
        prefix=f".{filename}.",
        suffix=".png",
    )
    temporary = Path(temporary_name)
    temporary_filename = temporary.name
    temporary_identity = _identity(os.fstat(descriptor))
    replaced = False
    try:
        entry = _entry_metadata(destination_dir, directory_fd, temporary_filename)
        if not stat.S_ISREG(entry.st_mode) or _identity(entry) != temporary_identity:
            raise InvalidSpriteName("sprite temporary file changed after creation")

        with os.fdopen(descriptor, "w+b") as stream:
            descriptor = -1
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
            opened_identity = _identity(os.fstat(stream.fileno()))

        entry = _entry_metadata(destination_dir, directory_fd, temporary_filename)
        if (
            opened_identity != temporary_identity
            or not stat.S_ISREG(entry.st_mode)
            or _identity(entry) != temporary_identity
        ):
            raise InvalidSpriteName("sprite temporary file changed during write")

        _assert_directory_snapshot(
            sprite_root,
            sprite_name,
            root,
            destination_dir,
            root_identity,
            directory_identity,
        )
        _validate_replace_target(destination)
        if directory_fd is not None:
            os.replace(
                temporary_filename,
                filename,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
        else:
            os.replace(temporary, destination)
        replaced = True

        final_metadata = _entry_metadata(destination_dir, directory_fd, filename)
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or _identity(final_metadata) != temporary_identity
        ):
            raise InvalidSpriteName("sprite frame changed during replacement")
        _assert_directory_snapshot(
            sprite_root,
            sprite_name,
            root,
            destination_dir,
            root_identity,
            directory_identity,
        )
        if directory_fd is not None:
            os.fsync(directory_fd)
    except BaseException:
        if replaced:
            _safe_unlink_entry(
                destination_dir,
                directory_fd,
                filename,
                temporary_identity,
            )
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _safe_unlink_entry(
            destination_dir,
            directory_fd,
            temporary_filename,
            temporary_identity,
        )
        if directory_fd is not None:
            os.close(directory_fd)
    return destination


def atomic_write_sprite_bytes(
    sprite_root: str | Path,
    sprite_name: str,
    filename: str,
    data: bytes,
) -> Path:
    """Atomically replace one sprite frame with in-memory bytes."""

    def _write(temporary: BinaryIO) -> None:
        temporary.write(data)

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
