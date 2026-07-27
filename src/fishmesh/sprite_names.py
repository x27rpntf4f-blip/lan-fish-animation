from __future__ import annotations

import ctypes
import inspect
import os
import stat
import tempfile
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
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


def _detect_directory_fd_replace_support() -> bool:
    if os.name != "posix" or os.rename not in os.supports_dir_fd:
        return False
    try:
        parameters = inspect.signature(os.replace).parameters
    except (TypeError, ValueError):
        return False
    return "src_dir_fd" in parameters and "dst_dir_fd" in parameters


_DIRECTORY_FD_REPLACE_SUPPORTED = _detect_directory_fd_replace_support()


def _supports_directory_fd_replace() -> bool:
    return os.name == "posix" and _DIRECTORY_FD_REPLACE_SUPPORTED


def _is_windows_platform() -> bool:
    return os.name == "nt"


@contextmanager
def _open_windows_directory_guard(directory: Path) -> Iterator[Callable[[], None]]:
    """Hold a non-delete-sharing Windows directory handle across replacement."""
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
    ]

    try:
        win_dll = ctypes.__dict__.get("WinDLL")
        if not callable(win_dll):
            raise AttributeError("ctypes.WinDLL is unavailable")
        kernel32 = win_dll("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise InvalidSpriteName("Windows directory locking is unavailable") from exc

    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [wintypes.HANDLE, ctypes.POINTER(ByHandleFileInformation)]
    get_information.restype = wintypes.BOOL
    get_final_path = kernel32.GetFinalPathNameByHandleW
    get_final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    get_final_path.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    file_share_read = 0x00000001
    file_share_write = 0x00000002
    open_existing = 3
    file_flag_open_reparse_point = 0x00200000
    file_flag_backup_semantics = 0x02000000
    file_attribute_reparse_point = 0x00000400
    handle = create_file(
        str(directory),
        0,
        file_share_read | file_share_write,
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise InvalidSpriteName("could not lock sprite directory without delete sharing")

    expected_path = os.path.normcase(os.path.abspath(directory))

    def _normalized_handle_path() -> str:
        required = get_final_path(handle, None, 0, 0)
        if required == 0:
            raise InvalidSpriteName("could not resolve locked sprite directory")
        buffer = ctypes.create_unicode_buffer(required + 1)
        if get_final_path(handle, buffer, len(buffer), 0) == 0:
            raise InvalidSpriteName("could not resolve locked sprite directory")
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return os.path.normcase(os.path.abspath(value))

    def verify() -> None:
        information = ByHandleFileInformation()
        if not get_information(handle, ctypes.byref(information)):
            raise InvalidSpriteName("could not verify locked sprite directory")
        if information.dwFileAttributes & file_attribute_reparse_point:
            raise InvalidSpriteName("sprite directory cannot be a Windows reparse point")
        metadata = directory.lstat()
        if getattr(metadata, "st_file_attributes", 0) & file_attribute_reparse_point:
            raise InvalidSpriteName("sprite directory cannot be a Windows reparse point")
        file_index = (information.nFileIndexHigh << 32) | information.nFileIndexLow
        if metadata.st_ino and metadata.st_ino != file_index:
            raise InvalidSpriteName("locked sprite directory identity changed")
        if _normalized_handle_path() != expected_path:
            raise InvalidSpriteName("locked sprite directory path changed")

    try:
        verify()
        yield verify
    finally:
        close_handle(handle)


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

    with ExitStack() as resources:
        directory_fd: int | None = None
        verify_native_guard: Callable[[], None] | None = None
        if _supports_directory_fd_replace():
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(destination_dir, directory_flags)
            resources.callback(os.close, directory_fd)
            if _identity(os.fstat(directory_fd)) != directory_identity:
                raise InvalidSpriteName("sprite directory changed while opening")
        elif _is_windows_platform():
            verify_native_guard = resources.enter_context(
                _open_windows_directory_guard(destination_dir)
            )
            verify_native_guard()
            _assert_directory_snapshot(
                sprite_root,
                sprite_name,
                root,
                destination_dir,
                root_identity,
                directory_identity,
            )
        else:
            raise InvalidSpriteName("safe atomic sprite replacement is unavailable")

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
            if verify_native_guard is not None:
                verify_native_guard()
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
            if verify_native_guard is not None:
                verify_native_guard()
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
