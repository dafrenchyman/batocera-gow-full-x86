"""Local-only mounted-library selection. This module never connects to Wolf."""

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from batocera_gow.runtime.media_catalog import (
    CatalogError,
    SystemRecord,
    load_catalog,
    object_record,
    text,
)

ROMS_DESTINATION = "/home/retro/userdata/roms"
BIOS_DESTINATION = "/home/retro/userdata/bios"
XISO_SECTOR_SIZE = 2048
XISO_VOLUME_OFFSET = 32 * XISO_SECTOR_SIZE


class MediaError(ValueError):
    """Configuration, access or discovery failed, not missing media."""


def inspect_xiso(path: Path) -> dict[str, object]:
    """Inspect raw XISO volume metadata without reading the filesystem tree.

    Args:
        path: Actual selected ISO, including stock's resolved squashfs member.

    Returns:
        Public descriptor and root-extent fields, with no paths or media bytes.
        These establish structure only, not bootability or title rendering.

    Raises:
        MediaError: If the image is unreadable, changes during inspection, or
            lacks a complete sector-32 XDVDFS descriptor and in-image root extent.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb", buffering=0) as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not before.st_mode & 0o444:
                msg = "XISO metadata requires a readable regular image"
                raise MediaError(msg)
            if before.st_size < XISO_VOLUME_OFFSET + XISO_SECTOR_SIZE:
                msg = "XISO volume descriptor is truncated"
                raise MediaError(msg)
            stream.seek(XISO_VOLUME_OFFSET)
            volume = stream.read(XISO_SECTOR_SIZE)
            after = os.fstat(stream.fileno())
    except OSError:
        # OS exceptions can contain private filenames, including in their cause.
        msg = "XISO metadata is unreadable"
        raise MediaError(msg) from None
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        msg = "XISO image changed during metadata inspection"
        raise MediaError(msg)
    magic = b"MICROSOFT*XBOX*MEDIA"
    if (
        len(volume) != XISO_SECTOR_SIZE
        or volume[:0x14] != magic
        or volume[0x7EC:] != magic
    ):
        msg = "XISO volume descriptor is invalid"
        raise MediaError(msg)
    root_sector = int.from_bytes(volume[0x14:0x18], "little")
    root_size = int.from_bytes(volume[0x18:0x1C], "little")
    if root_sector * XISO_SECTOR_SIZE + root_size > before.st_size:
        msg = "XISO root directory extent exceeds the image"
        raise MediaError(msg)
    return {
        "format": "xdvdfs",
        "sector_size": XISO_SECTOR_SIZE,
        "volume_offset": XISO_VOLUME_OFFSET,
        "image_size": before.st_size,
        "root_directory_sector": root_sector,
        "root_directory_size": root_size,
    }


@dataclass(frozen=True)
class EffectiveMount:
    """One Docker-inspected mount, with RW represented by writable."""

    source: str
    destination: str
    writable: bool
    kind: str = "bind"

    @classmethod
    def from_docker(cls, value: object) -> "EffectiveMount":
        """Validate a single Docker inspect Mounts item, failing closed."""
        try:
            record = object_record(value)
            if type(record.get("RW")) is not bool:
                msg = "Invalid effective mount writable observation"
                raise MediaError(msg)
            return cls(
                text(record.get("Source")),
                text(record.get("Destination")),
                record.get("RW") is True,
                text(record.get("Type")),
            )
        except CatalogError as error:
            msg = "Invalid effective mount inspection"
            raise MediaError(msg) from error


@dataclass(frozen=True)
class ContentRoots:
    """Docker-host paths, never implicitly paths on the coordinator machine."""

    roms: str
    bios: str

    def __post_init__(self) -> None:
        """Require literal Docker-host paths; never expand or inspect host media."""
        for source in (self.roms, self.bios):
            path = PurePosixPath(source)
            if (
                not source.startswith("/")
                or str(path) != source
                or ".." in path.parts
                or any(ord(char) < ord(" ") or char in ":$" for char in source)
            ):
                msg = "Content source must be a literal absolute Docker-host path"
                raise MediaError(msg)

    @classmethod
    def from_environment(cls, values: Mapping[str, str]) -> "ContentRoots":
        """Resolve explicitly supplied environment values, without dotenv or I/O.

        Raises:
            MediaError: If either required source is missing or not a literal path.
        """
        return cls(
            values.get("BATOCERA_GOW_ROMS_ROOT", ""),
            values.get("BATOCERA_GOW_BIOS_ROOT", ""),
        )

    def wolf_mounts(self) -> list[str]:
        """Build Wolf test-app binds with fixed read-only destinations."""
        return [
            f"{self.roms}:{ROMS_DESTINATION}:ro",
            f"{self.bios}:{BIOS_DESTINATION}:ro",
        ]

    def validate_mounts(self, mounts: Sequence[EffectiveMount]) -> None:
        """Require unique inspected read-only content binds matching configuration.

        Args:
            mounts: Complete effective Docker mount observations, not desired TOML.

        Raises:
            MediaError: If evidence is missing, duplicated, writable or mismatched.
        """
        if len({mount.destination for mount in mounts}) != len(mounts):
            msg = "Duplicate effective mount destination"
            raise MediaError(msg)
        for source, destination in (
            (self.roms, ROMS_DESTINATION),
            (self.bios, BIOS_DESTINATION),
        ):
            matches = [mount for mount in mounts if mount.destination == destination]
            if (
                len(matches) != 1
                or matches[0].source != source
                or matches[0].writable is not False
                or matches[0].kind != "bind"
            ):
                msg = "Effective content mount mismatch"
                raise MediaError(msg)
            if any(
                PurePosixPath(mount.destination).is_relative_to(destination)
                and mount.destination != destination
                for mount in mounts
            ):
                msg = "Nested mount shadows selected content"
                raise MediaError(msg)


@dataclass(frozen=True)
class Candidate:
    """An eligible entry and its complete read-only member set."""

    relative_path: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class Eligibility:
    """Discovery result. Rejected incomplete sets are not launch failures."""

    stock: SystemRecord
    roms_view: Path
    candidates: tuple[Candidate, ...]
    rejected: int

    @property
    def system(self) -> str:
        """Return the stock ID without rediscovering catalog configuration."""
        return self.stock.system

    @property
    def disposition(self) -> str:
        """Distinguish selection eligibility from untested media absence."""
        return "eligible" if self.candidates else "Skipped: no compatible mounted media"


@dataclass(frozen=True)
class MediaMember:
    """Private member identity. Never include this record in public reports."""

    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class MediaSelection:
    """Private reproducible selection, not evidence of working emulation."""

    system: str
    entry: str
    members: tuple[MediaMember, ...]
    digest: str


class _IncompleteMediaError(ValueError):
    """A supported descriptor is missing or has unusable companion metadata."""


def _open_directory(path: Path) -> int:
    """Anchor each path component without following intermediate symlinks."""
    absolute = path.absolute()
    if ".." in absolute.parts:
        msg = "Directory containment violation"
        raise MediaError(msg)
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
    except OSError:
        os.close(directory)
        raise
    else:
        return directory


def _open_member(root: Path, relative: str) -> int:
    """Open below an anchored directory without following any member symlink."""
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or ".." in parts:
        msg = "Media containment violation"
        raise MediaError(msg)
    directory = _open_directory(root)
    try:
        for part in parts[:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
        return os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
    finally:
        os.close(directory)


def _read_member(
    root: Path, relative: str, *, descriptor: bool = False
) -> tuple[MediaMember, bytes]:
    """Read a regular member, refusing unreadable, changed or special files."""
    with os.fdopen(_open_member(root, relative), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not before.st_mode & 0o444:
            msg = "Media discovery requires readable regular files"
            raise MediaError(msg)
        if descriptor and before.st_size > 1024 * 1024:
            msg = "Descriptor exceeds one MiB"
            raise _IncompleteMediaError(msg)
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            if descriptor:
                chunks.append(chunk)
                if sum(map(len, chunks)) > 1024 * 1024:
                    msg = "Descriptor exceeds one MiB"
                    raise _IncompleteMediaError(msg)
        after = os.fstat(stream.fileno())
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            msg = "Media changed during discovery"
            raise MediaError(msg)
    return MediaMember(relative, digest.hexdigest(), before.st_size), b"".join(chunks)


def _walk_files(root: Path, relative: str) -> tuple[str, ...]:
    """Discover only a selected subtree, refusing links and inaccessible entries."""
    descriptor = _open_member(root, relative)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o444:
                msg = "Media discovery requires readable regular files"
                raise MediaError(msg)
            return (relative,)
        if not metadata.st_mode & 0o444 or not metadata.st_mode & 0o111:
            msg = "Media discovery cannot access system directory"
            raise MediaError(msg)
        found: list[str] = []
        with os.scandir(descriptor) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                if entry.is_symlink():
                    msg = "Media symlink discovery refused"
                    raise MediaError(msg)
                found.extend(
                    _walk_files(root, str(PurePosixPath(relative) / entry.name))
                )
        return tuple(found)
    finally:
        os.close(descriptor)


def _reference(entry: str, reference: str, system_directory: str) -> str:
    """Resolve companion names strictly inside the selected system directory."""
    normalized = reference.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        path.is_absolute()
        or not normalized
        or ":" in normalized
        or any(ord(char) < ord(" ") for char in normalized)
    ):
        msg = "Companion containment violation"
        raise MediaError(msg)
    parts = list(PurePosixPath(entry).parent.parts)
    base = PurePosixPath(system_directory)
    for part in path.parts:
        if part == "..":
            if len(parts) <= len(base.parts):
                msg = "Companion containment violation"
                raise MediaError(msg)
            parts.pop()
        else:
            parts.append(part)
    target = PurePosixPath(*parts)
    if not target.is_relative_to(base):
        msg = "Companion containment violation"
        raise MediaError(msg)
    return str(target)


def _gdi_track_reference(line: str) -> str:
    """Parse one track's filename without exposing descriptor text on failure."""
    match = re.fullmatch(
        r'\s*\d+\s+\d+\s+\d+\s+\d+\s+(?:"([^"]+)"|(\S+))\s+\d+\s*', line
    )
    if match is None:
        msg = "Malformed GDI track"
        raise _IncompleteMediaError(msg)
    return match.group(1) or match.group(2)


def _gdi_references(content: str) -> list[str]:
    """Require every declared GDI track, retaining descriptor-relative names."""
    lines = content.splitlines()
    try:
        count = int(lines[0])
        references = [_gdi_track_reference(line) for line in lines[1:]]
    except (ValueError, IndexError) as error:
        msg = "Malformed GDI descriptor"
        raise _IncompleteMediaError(msg) from error
    if len(references) != count:
        msg = "Malformed GDI descriptor"
        raise _IncompleteMediaError(msg)
    return references


def _descriptor_references(root: Path, entry: str, suffix: str) -> list[str]:
    """Read the supported playlist/descriptor grammar and require media members."""
    _, raw = _read_member(root, entry, descriptor=True)
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        msg = "Unsupported descriptor encoding"
        raise _IncompleteMediaError(msg) from error
    if suffix == ".m3u":
        references = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    elif suffix in {".cue", ".toc"}:
        references = [
            match.group(1) or match.group(2)
            for match in re.finditer(
                r'^\s*(?:FILE|DATAFILE|AUDIOFILE)\s+(?:"([^"]+)"|(\S+))',
                content,
                re.MULTILINE | re.IGNORECASE,
            )
        ]
    else:
        references = _gdi_references(content)
    if not references:
        msg = "Descriptor has no media references"
        raise _IncompleteMediaError(msg)
    return references


def _paired_references(root: Path, entry: str, suffix: str) -> list[str]:
    """Retain mandatory paired images and only the optional CCD subchannel."""
    if suffix == ".mdf":
        return [PurePosixPath(entry).with_suffix(".mds").name]
    if suffix != ".ccd":
        return []
    references = [PurePosixPath(entry).with_suffix(".img").name]
    optional = str(PurePosixPath(entry).with_suffix(".sub"))
    try:
        descriptor = _open_member(root, optional)
    except FileNotFoundError:
        pass
    else:
        os.close(descriptor)
        references.append(PurePosixPath(optional).name)
    return references


def _members(  # noqa: PLR0913 - recursive traversal keeps root, stock constraints, consumed members and cycle ancestry explicit.
    root: Path,
    entry: str,
    system_directory: str,
    consumed: set[str],
    supported: frozenset[str],
    *,
    active: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Preserve CUE, playlist, GDI, TOC and paired image relationships."""
    if entry in active:
        msg = "Cyclic media relationship"
        raise _IncompleteMediaError(msg)
    suffix = PurePosixPath(entry).suffix.lower()
    descriptor = _open_member(root, entry)
    try:
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if stat.S_ISDIR(metadata.st_mode):
        files = _walk_files(root, entry)
        if not files:
            msg = "Empty directory media"
            raise _IncompleteMediaError(msg)
        return files
    if not stat.S_ISREG(metadata.st_mode) or not metadata.st_mode & 0o444:
        msg = "Companion discovery requires readable regular files"
        raise MediaError(msg)
    references = (
        _descriptor_references(root, entry, suffix)
        if suffix in {".cue", ".m3u", ".gdi", ".toc"}
        else _paired_references(root, entry, suffix)
    )
    members = {entry}
    for reference in references:
        companion = _reference(entry, reference, system_directory)
        if (
            suffix == ".m3u"
            and PurePosixPath(companion).suffix.lower() not in supported
        ):
            msg = "Playlist references unsupported media"
            raise _IncompleteMediaError(msg)
        consumed.add(companion)
        try:
            members.update(
                _members(
                    root,
                    companion,
                    system_directory,
                    consumed,
                    supported,
                    active=active | {entry},
                )
            )
        except FileNotFoundError as error:
            msg = "Missing companion"
            raise _IncompleteMediaError(msg) from error
    return tuple(sorted(members))


def _system_files(roms_view: Path, directory: str) -> tuple[str, ...] | None:
    """Inspect one stock system directory; only its absence is a no-media result."""
    metadata = roms_view.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or not metadata.st_mode & 0o444
        or not metadata.st_mode & 0o111
    ):
        msg = "ROM mount discovery failed"
        raise MediaError(msg)
    try:
        descriptor = _open_member(roms_view, directory)
    except FileNotFoundError:
        return None
    else:
        try:
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                msg = "Stock system directory is not a directory"
                raise MediaError(msg)
        finally:
            os.close(descriptor)
    return _walk_files(roms_view, directory)


def _supported_entries(
    files: tuple[str, ...], supported: frozenset[str], directory: str
) -> set[str]:
    """Include stock-supported files and multi-file media directory entries."""
    entries = {
        entry for entry in files if PurePosixPath(entry).suffix.lower() in supported
    }
    for entry in files:
        for parent in PurePosixPath(entry).parents:
            if str(parent) != directory and parent.suffix.lower() in supported:
                entries.add(str(parent))
    return entries


def inspect_media(system: SystemRecord, roms_view: Path) -> Eligibility:
    """Discover stock-supported entries in an explicit view of the ROM mount.

    Args:
        system: Stock declaration including its exact directory.
        roms_view: Existing mounted ROM root in the executing filesystem namespace.
            The caller must first validate effective mounts for native use.

    Returns:
        Eligible complete entries or an explicit untested no-media disposition.

    Raises:
        MediaError: On access, symlink, containment or root discovery failures.
    """
    directory = system.rom_relative_directory
    if directory is None:
        msg = "Stock category is outside the ROM mount"
        raise MediaError(msg)
    try:
        files = _system_files(roms_view, directory)
        if files is None:
            return Eligibility(system, roms_view, (), 0)
        supported = frozenset(extension.lower() for extension in system.extensions)
        entries = _supported_entries(files, supported, directory)
        candidates: list[Candidate] = []
        rejected = 0
        consumed: set[str] = set()
        # Playlists first, then descriptors before independent image components.
        priority = {".m3u": 0, ".cue": 1, ".ccd": 1, ".gdi": 1, ".toc": 1}
        for entry in sorted(
            entries,
            key=lambda value: (
                priority.get(PurePosixPath(value).suffix.lower(), 2),
                value,
            ),
        ):
            if entry in consumed:
                continue
            try:
                members = _members(roms_view, entry, directory, consumed, supported)
                for member in members:
                    descriptor = _open_member(roms_view, member)
                    with os.fdopen(descriptor, "rb") as stream:
                        if not os.fstat(stream.fileno()).st_mode & 0o444:
                            msg = "Media discovery access denied"
                            raise MediaError(msg)
                candidates.append(Candidate(entry, members))
                consumed.update(set(members) - {entry})
            except _IncompleteMediaError:
                rejected += 1
        return Eligibility(
            system,
            roms_view,
            tuple(
                candidate
                for candidate in candidates
                if candidate.relative_path not in consumed
            ),
            rejected,
        )
    except OSError as error:
        msg = "Media filesystem discovery failed"
        raise MediaError(msg) from error


def select_media(
    eligible: Eligibility, choose_index: Callable[[int], int]
) -> MediaSelection:
    """Choose exactly once and hash all members; failures never trigger rerolls.

    Args:
        eligible: A successful read-only discovery result.
        choose_index: Injected random or deterministic choice in range(count).

    Raises:
        MediaError: If no candidate, invalid choice, changed input or read failure.
    """
    if not eligible.candidates:
        msg = "No compatible mounted media to select"
        raise MediaError(msg)
    index = choose_index(len(eligible.candidates))
    if not 0 <= index < len(eligible.candidates):
        msg = "Invalid selection index"
        raise MediaError(msg)
    candidate = eligible.candidates[index]
    try:
        system = eligible.stock
        directory = system.rom_relative_directory
        supported = frozenset(extension.lower() for extension in system.extensions)
        if (
            directory is None
            or _members(
                eligible.roms_view, candidate.relative_path, directory, set(), supported
            )
            != candidate.members
        ):
            msg = "Selected media relationships changed"
            raise MediaError(msg)
        members = tuple(
            _read_member(eligible.roms_view, member)[0] for member in candidate.members
        )
    except (OSError, _IncompleteMediaError) as error:
        msg = "Selected media changed or cannot be read"
        raise MediaError(msg) from error
    identity = {
        "system": eligible.system,
        "entry": candidate.relative_path,
        "members": [
            [member.relative_path, member.sha256, member.size] for member in members
        ],
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return MediaSelection(eligible.system, candidate.relative_path, members, digest)


def write_selection(path: Path, selection: MediaSelection) -> None:
    """Atomically publish an exclusive private record, never copying media bytes.

    The parent must already be an owner-only directory owned by this user.
    Existing records are never overwritten, including after a failed attempt.
    """
    try:
        value = {
            "schema": 1,
            "system": selection.system,
            "entry": selection.entry,
            "digest": selection.digest,
            "members": [
                [member.relative_path, member.sha256, member.size]
                for member in selection.members
            ],
        }
        directory = _open_directory(path.parent)
        try:
            parent = os.fstat(directory)
            if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
                msg = "Private record parent must be owner-only"
                raise MediaError(msg)
            temporary = ".selection-" + secrets.token_hex(16)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(value, stream, sort_keys=True)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                # Link publication is atomic and refuses an existing destination.
                os.link(
                    temporary,
                    path.name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
            finally:
                os.unlink(temporary, dir_fd=directory)
        finally:
            os.close(directory)
    except OSError as error:
        msg = "Private selection record creation failed"
        raise MediaError(msg) from error


def read_selection(
    path: Path, roms_view: Path, *, catalog_path: Path | None = None
) -> MediaSelection:
    """Reproduce the recorded entry only, failing on changed identity or members."""
    try:
        with os.fdopen(
            _open_member(path.parent, path.name), "r", encoding="utf-8"
        ) as stream:
            metadata = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077
            ):
                msg = "Selection record is not owner-only"
                raise MediaError(msg)
            if metadata.st_size > 1024 * 1024:
                msg = "Selection record is too large"
                raise MediaError(msg)
            record = object_record(json.load(stream))
        catalog = load_catalog() if catalog_path is None else load_catalog(catalog_path)
        system = catalog.system(text(record.get("system")))
        entry = text(record.get("entry"))
        directory = system.rom_relative_directory
        entry_path = PurePosixPath(entry)
        supported = frozenset(extension.lower() for extension in system.extensions)
        if (
            directory is None
            or entry_path.is_absolute()
            or ".." in entry_path.parts
            or not entry_path.is_relative_to(directory)
            or entry_path.suffix.lower() not in supported
        ):
            msg = "Recorded media containment or format changed"
            raise MediaError(msg)
        candidate = Candidate(
            entry, _members(roms_view, entry, directory, set(), supported)
        )
        selection = select_media(
            Eligibility(system, roms_view, (candidate,), 0), lambda _count: 0
        )
        members = [
            [member.relative_path, member.sha256, member.size]
            for member in selection.members
        ]
        if (
            record.get("schema") != 1
            or selection.digest != record.get("digest")
            or members != record.get("members")
        ):
            msg = "Recorded media identity changed"
            raise MediaError(msg)
    except (
        OSError,
        CatalogError,
        UnicodeError,
        json.JSONDecodeError,
        _IncompleteMediaError,
    ) as error:
        msg = "Private selection record cannot be reproduced"
        raise MediaError(msg) from error
    else:
        return selection
