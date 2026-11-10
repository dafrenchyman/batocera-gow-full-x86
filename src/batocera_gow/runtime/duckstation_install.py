"""Install the one project-owned PSX catalog addition without replacing user files."""

import os
import shlex
import stat
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

OVERRIDE_NAME = "es_systems_gow_duckstation.cfg"
MAX_CATALOG_BYTES = 1024 * 1024
PRIVATE_DIRECTORY_MODE = 0o700
MIN_COMMAND_WORDS = 2
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _directory(stack: ExitStack, parent: int, name: str) -> int:
    """Borrow a parent and register each opened directory for cleanup."""
    descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    stack.callback(os.close, descriptor)
    return descriptor


def _userdata(stack: ExitStack, home: Path, uid: int, gid: int) -> int:
    """Open owned userdata through pinned no-follow directory descriptors."""
    current = os.open("/", DIRECTORY_FLAGS)
    stack.callback(os.close, current)
    for component in home.parts[1:]:
        current = _directory(stack, current, component)
    for name in (None, "userdata", "system", "configs", "emulationstation"):
        if name is not None:
            parent_info = os.fstat(current)
            created_gid = (
                parent_info.st_gid
                if parent_info.st_mode & stat.S_ISGID
                else os.getegid()
            )
            try:
                os.mkdir(name, PRIVATE_DIRECTORY_MODE, dir_fd=current)
            except FileExistsError:
                pass
            else:
                child = _directory(stack, current, name)
                created = os.fstat(child)
                if (
                    (created.st_uid, created.st_gid) != (os.geteuid(), created_gid)
                    or stat.S_IMODE(created.st_mode) & 0o777 != PRIVATE_DIRECTORY_MODE
                    # Enumerate the pinned FD; a path lookup would reopen a race.
                    or os.listdir(child)  # noqa: PTH208
                ):
                    message = "New DuckStation override directory was substituted"
                    raise RuntimeError(message)
                os.fchown(child, uid, gid)
                os.fchmod(child, 0o755)
            current = _directory(stack, current, name)
        info = os.fstat(current)
        if (info.st_uid, info.st_gid) != (uid, gid):
            message = "Unsafe DuckStation override directory ownership"
            raise RuntimeError(message)
    return current


def _publish(current: int, expected: bytes, uid: int, gid: int) -> str:
    """Publish complete bytes exclusively; unwind each successfully owned resource."""
    # The app can rename entries in its parent. Pin a root-only staging
    # directory so it cannot substitute the source between write/chown and link.
    with ExitStack() as stack:
        temporary = ".gow-duckstation-" + os.urandom(16).hex()
        os.mkdir(temporary, PRIVATE_DIRECTORY_MODE, dir_fd=current)
        staging = _directory(stack, current, temporary)
        info = os.fstat(staging)
        parent = os.fstat(current)
        staging_gid = parent.st_gid if parent.st_mode & stat.S_ISGID else os.getegid()
        if (
            (info.st_uid, info.st_gid) != (os.geteuid(), staging_gid)
            or stat.S_IMODE(info.st_mode) & 0o777 != PRIVATE_DIRECTORY_MODE
            # This descriptor pins the root-only publication staging directory.
            or os.listdir(staging)  # noqa: PTH208
        ):
            message = "Unsafe DuckStation override publication directory"
            raise RuntimeError(message)
        stack.callback(os.rmdir, temporary, dir_fd=current)
        descriptor = os.open(
            "override",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=staging,
        )
        stack.callback(os.unlink, "override", dir_fd=staging)
        stack.callback(os.close, descriptor)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(expected)
            stream.flush()
            os.fsync(descriptor)
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, 0o644)
        try:
            os.link(
                "override",
                OVERRIDE_NAME,
                src_dir_fd=staging,
                dst_dir_fd=current,
                follow_symlinks=False,
            )
        except FileExistsError:
            return "preserved-concurrent-destination"
    return "installed"


def _read_catalog(directory: int, name: str) -> bytes:
    """Read bounded regular-file bytes without root-opening a user device."""
    # O_PATH inspects a user device/FIFO/symlink without opening it for root I/O.
    descriptor = os.open(name, os.O_PATH | os.O_NOFOLLOW, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > MAX_CATALOG_BYTES
        ):
            message = "Unsafe or oversized catalog file"
            raise ValueError(message)
        with Path(f"/proc/self/fd/{descriptor}").open("rb") as stream:
            data = stream.read(MAX_CATALOG_BYTES + 1)
        if len(data) > MAX_CATALOG_BYTES:
            message = "Oversized catalog file"
            raise ValueError(message)
        return data
    finally:
        os.close(descriptor)


def _catalog_conflict(directory: int) -> str | None:
    """Return a preservation disposition for unreadable or overlapping catalogs."""
    for name in os.listdir(directory):
        if name == OVERRIDE_NAME or not (
            name in ("es_systems.cfg", "es_systems_custom.cfg")
            or (name.startswith("es_systems_") and name.endswith(".cfg"))
        ):
            continue
        try:
            # Stock Expat rejects external entities and bounds entity amplification;
            # _read_catalog separately enforces the owned regular-file byte bound.
            root = ET.fromstring(_read_catalog(directory, name))  # noqa: S314
        except (OSError, ValueError, ET.ParseError):
            return "preserved-unreadable-user-catalog"
        for system in root.findall("system"):
            if system.findtext("name") == "psx" and (
                system.find("command") is not None
                or any("command" in element.attrib for element in system.iter())
            ):
                return "preserved-conflicting-psx-command"
    return None


def install_override(home: Path, uid: int, gid: int, asset: Path) -> str:
    """Install absent XML in owned userdata, returning a fixed disposition.

    Existing expected bytes are a no-op. Modified destinations, unsafe files and
    overlapping PSX commands are preserved and reported, never given an implicit
    overlay ordering. Directory descriptors keep root writes/chowns off paths
    that the app can substitute. The caller owns the profile's startup lease.

    Args:
        home: Absolute profile home whose userdata belongs to the app identity.
        uid: App user receiving newly created directories and the override.
        gid: App group receiving newly created directories and the override.
        asset: Explicit packaged partial PSX catalog, never inferred from source.

    Returns:
        A stable install, no-op or preservation disposition.

    Raises:
        OSError: If descriptor traversal or publication fails.
        RuntimeError: If userdata directories do not belong to the app identity.
    """
    expected = asset.read_bytes()
    if not home.is_absolute() or ".." in home.parts or home == Path("/"):
        message = "Unsafe DuckStation override home"
        raise RuntimeError(message)
    with ExitStack() as stack:
        current = _userdata(stack, home, uid, gid)

        disposition = "installed"
        try:
            existing = _read_catalog(current, OVERRIDE_NAME)
        except FileNotFoundError:
            existing = None
        except ValueError:
            return "preserved-modified-destination"
        if existing is not None:
            if existing != expected:
                return "preserved-modified-destination"
            disposition = "already-installed"
        conflict = _catalog_conflict(current)
        if conflict is not None:
            return conflict
        if existing is not None:
            return disposition
        # ES merges catalogs at startup. Install-if-missing is not migration.
        return _publish(current, expected, uid, gid)


def launcher_environment(
    installed: Path, asset: Path, environment: Mapping[str, str]
) -> dict[str, str]:
    """Apply the installed PSX command's PATH prefix at the direct native seam.

    Native tests use stock emulatorlauncher directly, not ES shell expansion.
    Require the actual installed partial command to match the shipped asset so
    tests cannot qualify a correction absent from ordinary frontend launches.

    Args:
        installed: Expected installed override inside the selected userdata.
        asset: Explicit packaged reference catalog.
        environment: Borrowed launch environment, left unchanged.

    Returns:
        A copied environment with only the installed wrapper PATH prefix added.

    Raises:
        RuntimeError: If installation or the pinned command contract differs.
    """
    descriptor = os.open(installed.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        expected = asset.read_bytes()
        if (
            _read_catalog(descriptor, installed.name) != expected
            or _catalog_conflict(descriptor) is not None
        ):
            message = (
                "Expected installed DuckStation PSX command is missing, "
                "modified or conflicting"
            )
            raise RuntimeError(message)
    finally:
        os.close(descriptor)
    # This is the packaged reference asset, matched byte-for-byte above.
    command = shlex.split(
        ET.fromstring(expected).findtext("system/command", ""),  # noqa: S314
    )
    if (
        len(command) < MIN_COMMAND_WORDS
        or command[1] != "/usr/bin/emulatorlauncher"
        or not command[0].endswith(":$PATH")
        or not command[0].startswith("PATH=/opt/gow-full-x86/emulator-wrappers")
    ):
        message = "Packaged DuckStation PSX command contract differs"
        raise RuntimeError(message)
    result = dict(environment)
    result["PATH"] = command[0][5:-6] + ":" + result.get("PATH", "")
    return result
