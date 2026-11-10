"""Capture complete stock metadata and verify exact Docker-save layers."""

import argparse
import base64
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import NotRequired, TypedDict

from batocera_gow.provenance import project_mounts

BUILDER_PYTHON = "/opt/batocera-gow/bin/python"


class Entry(TypedDict):
    """Metadata compared without following stock symlinks."""

    type: int
    mode: int
    uid: int
    gid: int
    mtime_ns: NotRequired[int]
    xattrs: dict[str, str]
    size: NotRequired[int]
    sha256: NotRequired[str]
    target: NotRequired[str]
    device: NotRequired[list[int]]
    hardlinks: NotRequired[list[str]]


class Snapshot(TypedDict):
    """Versioned inventory of absolute paths within one filesystem root."""

    schema: int
    entries: dict[str, Entry]


def mapping(value: object) -> dict[str, object]:
    """Validate an external JSON object's string keys.

    Raises:
        ValueError: If the value is not an object with string keys.
    """
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        message = "expected a JSON object"
        raise ValueError(message)
    return {key: item for key, item in value.items() if isinstance(key, str)}


def read_object(path: Path) -> dict[str, object]:
    """Read an explicit UTF-8 JSON object, rejecting non-object records."""
    return mapping(json.loads(path.read_text(encoding="utf-8")))


def integer(value: object) -> int:
    """Require an integer rather than silently accepting JSON booleans."""
    if not isinstance(value, int) or isinstance(value, bool):
        message = "expected an integer"
        # Invalid external JSON data is a domain value error, not caller misuse.
        raise ValueError(message)  # noqa: TRY004
    return value


def string(value: object) -> str:
    """Require a JSON string at a declared data boundary."""
    if not isinstance(value, str):
        message = "expected a string"
        # Invalid external JSON data is a domain value error, not caller misuse.
        raise ValueError(message)  # noqa: TRY004
    return value


def read_snapshot(path: Path) -> Snapshot:
    """Validate serialized inventory fields before metadata operations."""
    document = read_object(path)
    entries: dict[str, Entry] = {}
    for name, raw in mapping(document.get("entries")).items():
        data = mapping(raw)
        entry: Entry = {
            "type": integer(data.get("type")),
            "mode": integer(data.get("mode")),
            "uid": integer(data.get("uid")),
            "gid": integer(data.get("gid")),
            "mtime_ns": integer(data.get("mtime_ns")),
            "xattrs": {
                key: string(value) for key, value in mapping(data.get("xattrs")).items()
            },
        }
        if "size" in data:
            entry["size"] = integer(data["size"])
        if "sha256" in data:
            entry["sha256"] = string(data["sha256"])
        if "target" in data:
            entry["target"] = string(data["target"])
        if "device" in data:
            device = data["device"]
            if not isinstance(device, list):
                message = "invalid device metadata"
                raise ValueError(message)
            entry["device"] = [integer(item) for item in device]
        if "hardlinks" in data:
            links = data["hardlinks"]
            if not isinstance(links, list):
                message = "invalid hardlink metadata"
                raise ValueError(message)
            entry["hardlinks"] = [string(item) for item in links]
        if set(data) != set(entry):
            message = "unsupported inventory fields"
            raise ValueError(message)
        entries[name] = entry
    return {"schema": integer(document.get("schema")), "entries": entries}


def digest_file(path: Path) -> str:
    """Hash file bytes in bounded chunks without interpreting archive content."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_local(path: Path, project_root: Path) -> Path:
    """Resolve an owned descendant and reject roots or symlink escapes."""
    resolved, root = path.resolve(), project_root.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        message = f"path escapes independent project: {resolved}"
        raise ValueError(message)
    return resolved


def validate_tar(path: Path) -> None:
    """Reject traversal, duplicate entries and writes through archive symlinks."""
    entries: dict[str, tarfile.TarInfo] = {}
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                message = f"unsafe archive member: {member.name}"
                raise ValueError(message)
            normalized = str(name)
            if normalized in entries:
                message = f"duplicate archive member: {normalized}"
                raise ValueError(message)
            entries[normalized] = member
            if member.islnk():
                target = PurePosixPath(member.linkname)
                if target.is_absolute() or ".." in target.parts:
                    message = f"unsafe hardlink: {member.linkname}"
                    raise ValueError(message)
    _validate_tar_links(entries)


def _validate_tar_links(entries: dict[str, tarfile.TarInfo]) -> None:
    """Refuse archive writes through non-directories and dangling hardlinks."""
    for name, member in entries.items():
        for parent in PurePosixPath(name).parents:
            ancestor = entries.get(str(parent))
            if ancestor is not None and not ancestor.isdir():
                message = f"archive traverses non-directory: {name}"
                raise ValueError(message)
        if member.islnk():
            target_member = entries.get(str(PurePosixPath(member.linkname)))
            if target_member is None or not (
                target_member.isfile() or target_member.islnk()
            ):
                message = f"hardlink does not name a file: {name}"
                raise ValueError(message)


def _metadata(path: Path, info: os.stat_result, name: str) -> Entry:
    """Capture common lstat metadata and reject unarchivable live sockets."""
    if stat.S_ISSOCK(info.st_mode):
        message = f"cannot archive a live socket: {name}"
        raise ValueError(message)
    return {
        "type": stat.S_IFMT(info.st_mode),
        "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mtime_ns": info.st_mtime_ns,
        "xattrs": {
            key: base64.b64encode(os.getxattr(path, key, follow_symlinks=False)).decode(
                "ascii"
            )
            for key in sorted(os.listxattr(path, follow_symlinks=False))
        },
    }


class Inventory:
    """Read a caller-selected root without following its symlinks."""

    def __init__(self, root: Path) -> None:
        """Borrow a root path; capture never changes its bytes or metadata."""
        self.root = root

    def capture(self) -> Snapshot:
        """Capture ownership, nanosecond times, xattrs, links and content hashes."""
        entries: dict[str, Entry] = {}
        groups: dict[tuple[int, int], list[str]] = {}
        hashes: dict[tuple[int, int], str] = {}
        pending = [(self.root, "/")]
        while pending:
            path, name = pending.pop()
            info = path.lstat()
            entry = _metadata(path, info, name)
            if stat.S_ISREG(info.st_mode):
                inode = (info.st_dev, info.st_ino)
                if inode not in hashes:
                    hashes[inode] = digest_file(path)
                entry["size"] = info.st_size
                entry["sha256"] = hashes[inode]
                groups.setdefault(inode, []).append(name)
            elif stat.S_ISLNK(info.st_mode):
                # Path.readlink normalizes spelling; stock target text is exact.
                entry["target"] = os.readlink(path)  # noqa: PTH115
            elif stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as children:
                    names = sorted(child.name for child in children)
                pending.extend(
                    (path / child, name.rstrip("/") + "/" + child)
                    for child in reversed(names)
                )
            elif stat.S_ISCHR(info.st_mode) or stat.S_ISBLK(info.st_mode):
                entry["device"] = [os.major(info.st_rdev), os.minor(info.st_rdev)]
            entries[name] = entry
        for paths in groups.values():
            if len(paths) > 1:
                for name in paths:
                    entries[name]["hardlinks"] = sorted(paths)
        return {"schema": 1, "entries": dict(sorted(entries.items()))}

    @staticmethod
    def compare(reference: Snapshot, candidate: Snapshot) -> dict[str, int]:
        """Refuse stock changes or additions outside isolated integration roots."""
        if reference["schema"] != 1 or candidate["schema"] != 1:
            message = "unsupported inventory schema"
            raise ValueError(message)
        old, new = reference["entries"], candidate["entries"]
        errors = []
        for name, entry in old.items():
            if name not in new:
                errors.append(f"removed stock path: {name}")
            elif new[name] != entry:
                fields = sorted(
                    key
                    for key in entry.keys() | new[name].keys()
                    if entry.get(key) != new[name].get(key)
                )
                errors.append(f"changed stock path: {name}: {', '.join(fields)}")
        for name in new.keys() - old.keys():
            allowed = name in (
                "/opt",
                "/nix",
                "/nix/store",
                "/opt/gow-full-x86",
            ) or name.startswith(("/opt/gow-full-x86/", "/nix/store/"))
            if not allowed:
                errors.append(f"unapproved addition: {name}")
            elif (
                name in ("/opt", "/nix", "/nix/store", "/opt/gow-full-x86")
                and new[name]["type"] != stat.S_IFDIR
            ):
                errors.append(f"addition parent is not a directory: {name}")
        if errors:
            raise ValueError("\n".join(errors))
        return {"verified_stock_paths": len(old), "added_paths": len(new) - len(old)}


def saved_image_layer(archive: Path, output: Path) -> Path:
    """Copy the sole Docker-save layer byte-for-byte without extracting it."""
    with tarfile.open(archive, "r:*") as saved:
        manifest_file = saved.extractfile("manifest.json")
        if manifest_file is None:
            message = "Docker save archive has no manifest"
            raise ValueError(message)
        with manifest_file:
            manifests = json.load(manifest_file)
        if not isinstance(manifests, list) or len(manifests) != 1:
            message = "inventory requires one flattened filesystem layer"
            raise ValueError(message)
        layers = mapping(manifests[0]).get("Layers")
        if not isinstance(layers, list) or len(layers) != 1:
            message = "inventory requires one flattened filesystem layer"
            raise ValueError(message)
        member = saved.getmember(string(layers[0]))
        if not member.isfile():
            message = "saved filesystem layer is not a regular file"
            raise ValueError(message)
        if shutil.disk_usage(output).free < member.size * 2:
            message = (
                f"inventory needs at least {member.size * 2} additional bytes "
                "for layer and unpack"
            )
            raise ValueError(message)
        source = saved.extractfile(member)
        if source is None:
            message = "saved filesystem layer is missing"
            raise ValueError(message)
        layer = output / "filesystem-layer.tar"
        with source, layer.open("xb") as destination:
            shutil.copyfileobj(source, destination, 8 * 1024 * 1024)
    return layer


# Each artifact, destination and configured execution boundary is independent.
def verify_image(  # noqa: PLR0913
    reference: Path,
    image: str,
    builder: str,
    output: Path,
    *,
    project_root: Path,
    docker: list[str],
) -> dict[str, object]:
    """Save an exact image and compare its sole layer in a networkless builder.

    Args:
        reference: Owned complete stock inventory.
        image: Local immutable image identity or selected local fixture tag.
        builder: Provisioned tools image with the installed package.
        output: Fresh owned verification destination.
        project_root: Explicit independent checkout root.
        docker: Configured Docker argv, borrowed from the command boundary.

    Returns:
        Stock comparison counts and the verified image selector.
    """
    output = checked_local(output, project_root)
    reference = checked_local(reference, project_root)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        message = "verification output must be fresh"
        raise ValueError(message)
    archive = output / "image-save.tar"
    with archive.open("xb") as stream:
        # Configured Docker argv and image data stay separate; no shell is used.
        subprocess.run(  # noqa: S603
            [*docker, "image", "save", image], stdout=stream, check=True
        )
    # Mounts come from declared inputs and checked owned destinations.
    subprocess.run(  # noqa: S603
        [
            *docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--name",
            "batocera-gow-full-experiment-inventory-" + os.urandom(4).hex(),
            *project_mounts(project_root.resolve()),
            "--mount",
            f"type=bind,src={output},dst=/work",
            "--mount",
            f"type=bind,src={reference},dst=/inputs/reference.json,readonly",
            "--entrypoint",
            BUILDER_PYTHON,
            builder,
            "-m",
            "batocera_gow.builder.inventory",
            "--project-root",
            "/project",
            "unpack-verify",
            "--archive",
            "/work/image-save.tar",
            "--saved-image",
            "--reference",
            "/inputs/reference.json",
            "--output",
            "/work",
        ],
        check=True,
    )
    result = read_object(output / "inventory-verification.json")
    result["image"] = image
    return result


def main() -> None:
    """Run installed inventory capture or networkless archive comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--root", required=True, type=Path)
    capture.add_argument("--output", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--reference", required=True, type=Path)
    verify.add_argument("--image", required=True)
    verify.add_argument("--builder", required=True)
    verify.add_argument("--output", type=Path)
    verify.add_argument("--docker", default=os.environ.get("DOCKER", "docker"))
    unpack = commands.add_parser("unpack-verify")
    unpack.add_argument("--archive", required=True, type=Path)
    unpack.add_argument("--saved-image", action="store_true")
    unpack.add_argument("--reference", required=True, type=Path)
    unpack.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "capture":
        args.output.write_text(
            json.dumps(Inventory(args.root).capture(), indent=2) + "\n",
            encoding="utf-8",
        )
        return
    if args.command == "verify":
        project_root = args.project_root.resolve()
        output = (
            args.output
            if args.output is not None
            else project_root / "output/gow-full-x86/inventory-verification"
        )
        docker = shlex.split(args.docker)
        if not docker:
            parser.error("--docker requires a nonempty executable argv")
        sys.stdout.write(
            json.dumps(
                verify_image(
                    args.reference,
                    args.image,
                    args.builder,
                    output,
                    project_root=project_root,
                    docker=docker,
                ),
                indent=2,
            )
            + "\n"
        )
        return
    output = args.output
    root = output / "unpacked"
    root.mkdir()
    (output / "tmp").mkdir(exist_ok=True)
    archive = (
        saved_image_layer(args.archive, output) if args.saved_image else args.archive
    )
    validate_tar(archive)
    # Validated archive and owned extraction root are passed as separate argv.
    subprocess.run(  # noqa: S603
        [
            "/usr/bin/tar",
            "--extract",
            "--file",
            str(archive),
            "--directory",
            str(root),
            "--numeric-owner",
            "--same-owner",
            "--same-permissions",
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--delay-directory-restore",
        ],
        check=True,
    )
    result = Inventory.compare(read_snapshot(args.reference), Inventory(root).capture())
    (output / "inventory-verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(root)
    if args.saved_image:
        archive.unlink()
        args.archive.unlink()


if __name__ == "__main__":
    main()
