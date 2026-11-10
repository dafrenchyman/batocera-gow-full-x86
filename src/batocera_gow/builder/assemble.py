"""Assemble both complete official root layers, the complete FAT tree, and SHARE."""

import argparse
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

from batocera_gow.builder.inventory import (
    Inventory,
    checked_local,
    digest_file,
    integer,
    mapping,
    read_object,
    read_snapshot,
    string,
    validate_tar,
)
from batocera_gow.provenance import declared_inputs, project_mounts

EFI_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
BASIC_TYPE = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"
LINUX_TYPE = "0fc63daf-8483-4772-8e79-3d69d8477de4"
STOCK_PARTITION_COUNT = 2
SQUASHFS_SUPERBLOCK_BYTES = 96
SQUASHFS_MAJOR_VERSION = 4


class Partition(TypedDict):
    """Validated partition geometry, with offsets and lengths in bytes."""

    number: int
    start: int
    sectors: int
    offset: int
    bytes: int
    type: str
    name: str


def positive_integer(value: object, field: str) -> int:
    """Require a positive JSON integer, excluding booleans."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        msg = f"{field} must be a positive integer"
        raise ValueError(msg)
    return value


def validate_partitions(table: object, disk_size: int) -> list[Partition]:
    """Validate two GPT partitions using reported sector geometry and bounds."""
    positive_integer(disk_size, "disk size")
    table = mapping(mapping(table).get("partitiontable"))
    if table.get("label") != "gpt" or table.get("unit") != "sectors":
        msg = "expected a GPT table measured in sectors"
        raise ValueError(msg)
    sector = positive_integer(table.get("sectorsize"), "sector size")
    if sector not in (512, 1024, 2048, 4096):
        msg = "unsupported sector size"
        raise ValueError(msg)
    first = positive_integer(table.get("firstlba"), "first usable GPT sector")
    last = positive_integer(table.get("lastlba"), "last usable GPT sector")
    if first > last or (last + 1) * sector > disk_size:
        msg = "GPT usable bounds exceed disk"
        raise ValueError(msg)
    partitions = table.get("partitions")
    if not isinstance(partitions, list) or len(partitions) != STOCK_PARTITION_COUNT:
        msg = "expected exactly FAT boot and ext4 SHARE partitions"
        raise ValueError(msg)
    result: list[Partition] = []
    for index, raw_partition in enumerate(partitions, 1):
        partition = mapping(raw_partition)
        start = positive_integer(partition.get("start"), "partition start")
        size = positive_integer(partition.get("size"), "partition size")
        end = start + size
        if start < first or end - 1 > last or end * sector > disk_size:
            msg = "partition exceeds GPT/disk bounds"
            raise ValueError(msg)
        result.append(
            {
                "number": index,
                "start": start,
                "sectors": size,
                "offset": start * sector,
                "bytes": size * sector,
                "type": str(partition.get("type", "")).lower(),
                "name": string(partition.get("name", "")),
            }
        )
    ordered = sorted(result, key=lambda part: part["offset"])
    if ordered[0]["offset"] + ordered[0]["bytes"] > ordered[1]["offset"]:
        msg = "overlapping partitions"
        raise ValueError(msg)
    if result[0]["type"] not in (EFI_TYPE, BASIC_TYPE) or result[1]["type"] not in (
        LINUX_TYPE,
        BASIC_TYPE,
    ):
        msg = "unexpected boot/SHARE GPT partition types"
        raise ValueError(msg)
    return result


def walk_types(root: Path) -> dict[str, bool]:
    """List path kinds without following absolute or relative stock symlinks."""
    entries: dict[str, bool] = {}
    pending = [(Path(root), "")]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as children:
            for child in children:
                relative = prefix + child.name
                is_directory = child.is_dir(follow_symlinks=False)
                entries[relative] = is_directory
                if is_directory:
                    pending.append((Path(child.path), relative + "/"))
    return entries


def path_conflicts(
    secondary: Mapping[str, bool], main: Mapping[str, bool]
) -> list[str]:
    """Only real directories may be shared by the two whole-root layers."""
    return sorted(
        name
        for name in secondary.keys() & main.keys()
        if not (secondary[name] and main[name])
    )


def squashfs_superblock(path: Path) -> dict[str, int]:
    """Read SquashFS v4 sizing without extraction or stock code execution."""
    with path.open("rb") as stream:
        block = stream.read(SQUASHFS_SUPERBLOCK_BYTES)
    if len(block) != SQUASHFS_SUPERBLOCK_BYTES or block[:4] != b"hsqs":
        msg = f"not a SquashFS image: {path}"
        raise ValueError(msg)
    inode_count = struct.unpack_from("<I", block, 4)[0]
    major = struct.unpack_from("<H", block, 28)[0]
    used = struct.unpack_from("<Q", block, 40)[0]
    if (
        major != SQUASHFS_MAJOR_VERSION
        or used < SQUASHFS_SUPERBLOCK_BYTES
        or used > path.stat().st_size
    ):
        msg = f"invalid SquashFS superblock: {path}"
        raise ValueError(msg)
    return {"bytes_used": used, "inode_count": inode_count}


def require_space(directory: Path, needed: int) -> None:
    """Refuse insufficient storage while retaining verified inputs."""
    free = shutil.disk_usage(directory).free
    if free < needed:
        msg = (
            f"insufficient storage: need {needed} remaining bytes, have {free}; "
            f"add {needed - free} bytes; verified input retained"
        )
        raise ValueError(msg)


def run(
    command: Sequence[str | Path],
    *,
    stdin_text: str | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute argv without a shell and propagate failures to its owner."""
    # Trusted tool argv is supplied by the builder/fixture boundary, never a shell.
    return subprocess.run(  # noqa: S603
        [str(arg) for arg in command], check=True, input=stdin_text, env=env, text=True
    )


def source_fingerprint(root: Path) -> str:
    """Hash every declared transitive source, asset and dependency input."""
    return string(declared_inputs(root)["sha256"])


def cached_assembly(
    output: Path, input_sha256: str, closure_bytes: int, *, project_root: Path
) -> dict[str, object]:
    """Reuse only complete artifacts with matching inputs and intact bytes."""
    try:
        manifest = _assembly_cache(
            output, input_sha256, closure_bytes, project_root=project_root
        )
    except (OSError, KeyError, ValueError) as error:
        msg = (
            f"existing assembly is incomplete, changed, or corrupt at {output}; "
            "choose a fresh --output directory; "
            "retained input need not be downloaded again"
        )
        raise ValueError(msg) from error
    else:
        return manifest


def _assembly_cache(
    output: Path, input_sha256: str, closure_bytes: int, *, project_root: Path
) -> dict[str, object]:
    """Validate cached input provenance and each independently hashed artifact."""
    manifest = read_object(output / "assembly-manifest.json")
    if (
        manifest.get("input_sha256") != input_sha256
        or manifest.get("assembly_source_sha256") != source_fingerprint(project_root)
        or manifest.get("closure_bytes") != closure_bytes
    ):
        msg = "assembly inputs changed"
        raise ValueError(msg)
    for name, key in (
        ("stock-root.tar", "stock_root_sha256"),
        ("stock-share.tar", "stock_share_sha256"),
        ("stock-manifest.json", "stock_manifest_sha256"),
        ("share-manifest.json", "share_manifest_sha256"),
    ):
        if digest_file(output / name) != manifest[key]:
            msg = f"cached artifact changed: {name}"
            raise ValueError(msg)
    return manifest


class Assembler:
    """Own disposable stock extraction products within one fresh output."""

    def __init__(
        self, image: Path, output: Path, closure_bytes: int = 0, *, project_root: Path
    ) -> None:
        """Configure a fresh output, compressed disk and explicit input root."""
        self.image = image
        self.output = output
        self.project_root = project_root
        self.closure_bytes = closure_bytes
        self.disk = self.output / "release.img"
        self.boot = self.output / "fat"
        self.root = self.output / "root"
        self.partitions: list[Partition] = []

    def decompressed_size(self) -> int:
        """Measure the complete decompressed disk before allocating products."""
        total = 0
        with gzip.open(self.image, "rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                total += len(block)
        if total == 0:
            msg = "empty compressed disk image"
            raise ValueError(msg)
        return total

    def unpack_disk(self, disk_size: int) -> None:
        """Decompress and validate GPT geometry and both filesystem kinds."""
        # The first bound includes the decompressed image and one full FAT copy.
        # Expanded layer sizes are measured before either layer is extracted.
        require_space(self.output, disk_size * 2 + self.closure_bytes * 3)
        with gzip.open(self.image, "rb") as source, self.disk.open("xb") as destination:
            shutil.copyfileobj(source, destination, 8 * 1024 * 1024)
        table = json.loads(
            # A declared owned disk is data for Debian's fixed sfdisk executable.
            subprocess.check_output(  # noqa: S603
                ["/usr/sbin/sfdisk", "--json", str(self.disk)], text=True
            )
        )
        self.partitions = validate_partitions(table, self.disk.stat().st_size)
        for partition, expected in zip(self.partitions, ("vfat", "ext4"), strict=True):
            # Partition offsets were validated against the complete disk bounds.
            filesystem = subprocess.check_output(  # noqa: S603
                [
                    "/usr/sbin/blkid",
                    "-p",
                    "-O",
                    str(partition["offset"]),
                    "-S",
                    str(partition["bytes"]),
                    "-s",
                    "TYPE",
                    "-o",
                    "value",
                    str(self.disk),
                ],
                text=True,
            ).strip()
            if filesystem != expected:
                msg = (
                    f"partition {partition['number']}: expected {expected}, "
                    f"found {filesystem}"
                )
                raise ValueError(msg)
        (self.output / "partitions.json").write_text(
            json.dumps(table, indent=2) + "\n", encoding="utf-8"
        )

    def extract_boot(self) -> None:
        """Copy the complete FAT tree and require both root images."""
        self.boot.mkdir()
        run(
            [
                "mcopy",
                "-s",
                "-p",
                "-m",
                "-i",
                f"{self.disk}@@{self.partitions[0]['offset']}",
                "::*",
                self.boot,
            ]
        )
        for filename in ("batocera", "rufomaculata"):
            image = self.boot / "boot" / filename
            if not image.is_file() or image.is_symlink():
                msg = f"required complete root layer missing: boot/{filename}"
                raise ValueError(msg)

    def layer_requirements(self) -> tuple[dict[str, dict[str, int]], int]:
        """Bound expanded archive and extraction storage for both full roots."""
        metadata: dict[str, dict[str, int]] = {}
        expanded = 0
        for name in ("batocera", "rufomaculata"):
            image = self.boot / "boot" / name
            superblock = squashfs_superblock(image)
            # Listing does not unpack, execute, or follow any release symlink.
            size = 0
            # The fixed listing tool reads only the declared stock layer image.
            with subprocess.Popen(  # noqa: S603
                ["/usr/bin/unsquashfs", "-lln", "-UTC", str(image)],
                stdout=subprocess.PIPE,
                text=True,
            ) as listing:
                if listing.stdout is None:
                    listing.kill()
                    message = "cannot open SquashFS listing pipe"
                    raise ValueError(message)
                with listing.stdout:
                    for line in listing.stdout:
                        match = re.match(
                            r"^[bcdlps-][rwxStTs-]{9}\s+\d+/\d+\s+(\d+)\s+", line
                        )
                        if match:
                            size += int(match.group(1))
                if listing.wait() != 0:
                    message = f"cannot list complete SquashFS: {name}"
                    raise ValueError(message)
            # Account for block rounding, xattrs, directory inodes and tar headers.
            size += superblock["inode_count"] * 8192
            metadata[name] = dict(superblock, estimated_expanded_bytes=size)
            expanded += size
        if expanded == 0:
            msg = "empty root layers"
            raise ValueError(msg)
        # Existing disk/FAT are already allocated. Allow extracted layers, merged
        # root, stock archive, SHARE archive and OCI packaging copies together.
        remaining = (
            expanded * 5 + self.partitions[1]["bytes"] * 3 + self.closure_bytes * 3
        )
        require_space(self.output, remaining)
        return metadata, remaining

    def extract_layers(self) -> None:
        """Merge complete roots, allowing shared real directories only."""
        for name in ("rufomaculata", "batocera"):
            destination = self.output / name
            run(
                [
                    "unsquashfs",
                    "-strict-errors",
                    "-no-progress",
                    "-xattrs",
                    "-d",
                    destination,
                    self.boot / "boot" / name,
                ]
            )
        secondary, main = self.output / "rufomaculata", self.output / "batocera"
        conflicts = path_conflicts(walk_types(secondary), walk_types(main))
        if conflicts:
            raise ValueError(
                "root-layer non-directory collisions: " + ", ".join(conflicts)
            )
        self.root.mkdir()
        for source in (secondary, main):
            run(
                [
                    "rsync",
                    "-aHAX",
                    "--numeric-ids",
                    str(source) + "/",
                    str(self.root) + "/",
                ]
            )
        for reserved in ("nix", "opt/gow-full-x86"):
            path = self.root / reserved
            if os.path.lexists(path):
                msg = f"stock path collides with isolated additions: /{reserved}"
                raise ValueError(msg)
        opt = self.root / "opt"
        if os.path.lexists(opt) and (opt.is_symlink() or not opt.is_dir()):
            msg = "stock /opt is not a real directory"
            raise ValueError(msg)
        boot = self.root / "boot"
        if os.path.lexists(boot) and (boot.is_symlink() or not boot.is_dir()):
            msg = "stock /boot is not a real directory"
            raise ValueError(msg)
        if boot.exists() and any(boot.iterdir()):
            msg = "stock root /boot is not an empty mountpoint"
            raise ValueError(msg)
        boot.mkdir(exist_ok=True)
        run(["rsync", "-aHAX", "--numeric-ids", str(self.boot) + "/", str(boot) + "/"])

    def export_share(self) -> None:
        """Export the entire read-only SHARE filesystem with xattrs and ACLs."""
        share = self.partitions[1]
        # guestfish assigns this explicitly attached raw drive /dev/sda. Validate
        # the selected filesystem again inside the read-only guestfs appliance.
        device = f"/dev/sda{share['number']}"
        environment = dict(
            os.environ,
            LIBGUESTFS_BACKEND="direct",
            LIBGUESTFS_BACKEND_SETTINGS="force_tcg",
            LIBGUESTFS_CACHEDIR=str(self.output / "guestfs-cache"),
            LIBGUESTFS_TMPDIR=str(self.output / "tmp"),
        )
        (self.output / "guestfs-cache").mkdir()
        # The read-only appliance consumes only the explicitly owned raw disk.
        filesystem = subprocess.check_output(  # noqa: S603
            [
                "/usr/bin/guestfish",
                "--ro",
                "--format=raw",
                "-a",
                str(self.disk),
                "run",
                ":",
                "vfs-type",
                device,
            ],
            env=environment,
            text=True,
        ).strip()
        if filesystem != "ext4":
            msg = f"guestfs SHARE partition type is not ext4: {filesystem}"
            raise ValueError(msg)
        run(
            [
                "guestfish",
                "--ro",
                "--format=raw",
                "-a",
                self.disk,
                "-m",
                device + ":/:ro",
                "tar-out",
                "/",
                self.output / "stock-share.tar",
                "numericowner:true",
                "xattrs:true",
                "acls:true",
            ],
            env=environment,
        )
        # Seed is inventoried separately, including filesystem-created entries.
        validate_tar(self.output / "stock-share.tar")
        seed = self.output / "share-inventory-root"
        seed.mkdir()
        run(
            [
                "tar",
                "-xf",
                self.output / "stock-share.tar",
                "-C",
                seed,
                "--numeric-owner",
                "--same-owner",
                "--same-permissions",
                "--acls",
                "--xattrs",
                "--xattrs-include=*",
                "--delay-directory-restore",
            ]
        )
        (self.output / "share-manifest.json").write_text(
            json.dumps(Inventory(seed).capture(), indent=2) + "\n", encoding="utf-8"
        )

    def assemble(self) -> dict[str, object]:
        """Export complete stock roots and SHARE, refusing mid-run input drift."""
        initial_source = source_fingerprint(self.project_root)
        if any(self.output.iterdir()):
            msg = "assembly output must be a fresh empty directory"
            raise ValueError(msg)
        (self.output / "tmp").mkdir()
        disk_size = self.decompressed_size()
        self.unpack_disk(disk_size)
        self.extract_boot()
        layers, remaining = self.layer_requirements()
        self.extract_layers()
        self.export_share()
        manifest = Inventory(self.root).capture()
        (self.output / "stock-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        run(
            [
                "tar",
                "--create",
                "--file",
                self.output / "stock-root.tar",
                "--directory",
                self.root,
                "--format=posix",
                "--numeric-owner",
                "--acls",
                "--xattrs",
                "--xattrs-include=*",
                "--pax-option=delete=atime,delete=ctime",
                ".",
            ]
        )
        result: dict[str, object] = {
            "schema": 1,
            "disk_bytes": disk_size,
            "partitions": self.partitions,
            "squashfs": layers,
            "remaining_space_bound_bytes": remaining,
            "closure_bytes": self.closure_bytes,
            "stock_paths": len(manifest["entries"]),
            "stock_root_sha256": digest_file(self.output / "stock-root.tar"),
            "stock_share_sha256": digest_file(self.output / "stock-share.tar"),
            "stock_manifest_sha256": digest_file(self.output / "stock-manifest.json"),
            "share_manifest_sha256": digest_file(self.output / "share-manifest.json"),
            "assembly_source_sha256": initial_source,
        }
        package_list = Path("/builder-packages.tsv")
        if package_list.is_file():
            shutil.copyfile(package_list, self.output / "builder-packages.tsv")
        if source_fingerprint(self.project_root) != initial_source:
            msg = "declared build inputs changed during assembly"
            raise ValueError(msg)
        (self.output / "assembly-manifest.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        # These are disposable products created by this assembly only. Keep
        # the verified compressed input and all archives/manifests.
        for temporary in (
            self.boot,
            self.root,
            self.output / "batocera",
            self.output / "rufomaculata",
            self.output / "share-inventory-root",
            self.output / "guestfs-cache",
            self.output / "tmp",
        ):
            shutil.rmtree(temporary)
        self.disk.unlink()
        return result


# Keep independently owned input/output paths and execution configuration explicit.
def assemble_in_builder(  # noqa: PLR0913
    image: Path,
    output: Path,
    builder: str,
    closure_bytes: int,
    *,
    project_root: Path,
    docker: list[str],
) -> dict[str, object]:
    """Check official bytes and run installed assembly without networking."""
    image = checked_local(image, project_root)
    output = checked_local(output, project_root)
    if not image.is_file():
        msg = "verified compressed input is missing"
        raise ValueError(msg)
    release = read_object(project_root / "build-assets/release.json")
    md5, sha256 = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    with image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    if md5.hexdigest() != release["compressed_md5"]:
        msg = "official compressed image checksum mismatch"
        raise ValueError(msg)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        manifest = cached_assembly(
            output, sha256.hexdigest(), closure_bytes, project_root=project_root
        )
        manifest["builder"] = builder
        return manifest
    # Docker configuration and validated mounts stay argv data without a shell.
    subprocess.run(  # noqa: S603
        [
            *docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--name",
            "batocera-gow-full-experiment-assembly-" + uuid.uuid4().hex[:12],
            "--mount",
            f"type=bind,src={image},dst=/inputs/release.img.gz,readonly",
            *project_mounts(project_root.resolve()),
            "--mount",
            f"type=bind,src={output},dst=/work",
            builder,
            "--project-root",
            "/project",
            "--inside",
            "--image",
            "/inputs/release.img.gz",
            "--output",
            "/work",
            "--input-sha256",
            sha256.hexdigest(),
            "--closure-bytes",
            str(closure_bytes),
        ],
        check=True,
    )
    manifest = read_object(output / "assembly-manifest.json")
    manifest["builder"] = builder
    return manifest


def extract_archive(archive: Path, root: Path) -> None:
    """Extract a validated archive while retaining stock metadata."""
    validate_tar(archive)
    run(
        [
            "tar",
            "-xf",
            archive,
            "-C",
            root,
            "--numeric-owner",
            "--same-owner",
            "--same-permissions",
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--delay-directory-restore",
        ]
    )


# Independent archive inputs deliberately remain visible at their cache boundary.
def package_inputs(  # noqa: PLR0913
    stock_root: Path,
    reference: Path,
    bridge: Path,
    runtime: Path,
    seed: Path,
    *,
    project_root: Path,
) -> dict[str, str]:
    """Identify complete archive inputs and timestamp-independent staged code."""
    runtime_manifest = Inventory(runtime).capture()
    for entry in runtime_manifest["entries"].values():
        entry.pop("mtime_ns", None)
    return {
        "stock_root_sha256": digest_file(stock_root),
        "reference_sha256": digest_file(reference),
        "bridge_sha256": digest_file(bridge),
        "seed_sha256": digest_file(seed),
        "runtime_sha256": hashlib.sha256(
            json.dumps(runtime_manifest, sort_keys=True).encode()
        ).hexdigest(),
        "assembly_source_sha256": source_fingerprint(project_root),
    }


# This is one atomic multi-artifact packaging operation with explicit ownership.
def package_root(  # noqa: PLR0913, PLR0917
    stock_root: Path,
    reference: Path,
    bridge: Path,
    runtime: Path,
    seed: Path,
    output: Path,
    *,
    project_root: Path,
) -> dict[str, object]:
    """Package isolated additions without altering any stock metadata."""
    if any(output.iterdir()):
        msg = "packaging output must be fresh"
        raise ValueError(msg)
    inputs = package_inputs(
        stock_root, reference, bridge, runtime, seed, project_root=project_root
    )
    reference_snapshot = read_snapshot(reference)
    # Stock archive, closure, unpacked root, final tar and subsequent Docker
    # import must fit without borrowing any unrelated build's storage.
    archive_bytes = (
        Path(stock_root).stat().st_size
        + Path(bridge).stat().st_size
        + Path(seed).stat().st_size
    )
    require_space(output, archive_bytes * 4)
    (output / "tmp").mkdir()
    root = output / "root"
    root.mkdir()
    extract_archive(stock_root, root)
    Inventory.compare(reference_snapshot, Inventory(root).capture())
    # Closure tar must contain only its isolated store paths. Even a harmless
    # archive entry for /usr would otherwise overwrite stock directory metadata.
    with tarfile.open(bridge, "r:*") as archive:
        for member in archive:
            name = member.name.rstrip("/")
            if name not in ("nix", "nix/store") and not name.startswith("nix/store/"):
                msg = f"closure path outside /nix/store: {name}"
                raise ValueError(msg)
    extract_archive(bridge, root)
    destination = root / "opt/gow-full-x86"
    destination.mkdir(parents=True)
    run(
        [
            "rsync",
            "-aHAX",
            "--numeric-ids",
            "--chown=0:0",
            "--chmod=go-w",
            str(runtime) + "/",
            str(destination) + "/",
        ]
    )
    run(["setfacl", "--recursive", "--remove-all", "--remove-default", destination])
    shutil.copyfile(seed, destination / "stock-share.tar")
    (destination / "stock-share.tar").chmod(0o644)
    # Creation of allowed children changes stock parent directory timestamps.
    # Restore them before both the complete comparison and final archive.
    for name, entry in reference_snapshot["entries"].items():
        if entry["type"] == stat.S_IFDIR:
            directory = root / name.lstrip("/")
            os.chown(directory, entry["uid"], entry["gid"], follow_symlinks=False)
            directory.chmod(entry["mode"], follow_symlinks=False)
            mtime_ns = integer(entry.get("mtime_ns"))
            os.utime(
                directory,
                ns=(mtime_ns, mtime_ns),
                follow_symlinks=False,
            )
    comparison = Inventory.compare(reference_snapshot, Inventory(root).capture())
    result: dict[str, object] = dict(comparison)
    run(
        [
            "tar",
            "--create",
            "--file",
            output / "final-root.tar",
            "--directory",
            root,
            "--format=posix",
            "--numeric-owner",
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--pax-option=delete=atime,delete=ctime",
            ".",
        ]
    )
    if (
        package_inputs(
            stock_root, reference, bridge, runtime, seed, project_root=project_root
        )
        != inputs
    ):
        msg = "package inputs changed during assembly"
        raise ValueError(msg)
    result["final_root_sha256"] = digest_file(output / "final-root.tar")
    result["inputs"] = inputs
    (output / "package-manifest.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(root)
    shutil.rmtree(output / "tmp")
    return result


def package_command(
    argv: Sequence[str], *, project_root: Path, docker: list[str]
) -> dict[str, object]:
    """Dispatch explicit package inputs to the installed networkless builder."""
    parser = argparse.ArgumentParser(
        description="Create a single metadata-preserving runtime root archive"
    )
    for flag in ("stock-root", "reference", "bridge", "runtime", "seed", "output"):
        parser.add_argument("--" + flag, required=True, type=Path)
    parser.add_argument("--builder")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.inside:
        return package_root(
            args.stock_root,
            args.reference,
            args.bridge,
            args.runtime,
            args.seed,
            args.output,
            project_root=project_root,
        )
    if not args.builder:
        parser.error("--builder is required")
    output = checked_local(args.output, project_root)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("stock_root", "reference", "bridge", "runtime", "seed"):
        setattr(args, name, checked_local(getattr(args, name), project_root))
    if any(output.iterdir()):
        try:
            expected = package_inputs(
                args.stock_root,
                args.reference,
                args.bridge,
                args.runtime,
                args.seed,
                project_root=project_root,
            )
            manifest = _package_cache(output, expected)
        except (OSError, KeyError, ValueError) as error:
            msg = (
                f"existing packaging is incomplete, changed, or corrupt at {output}; "
                "choose a fresh --output directory"
            )
            raise ValueError(msg) from error
        else:
            return manifest
    command = [
        *docker,
        "run",
        "--rm",
        "--network",
        "none",
        "--name",
        "batocera-gow-full-experiment-package-" + uuid.uuid4().hex[:12],
        *project_mounts(project_root.resolve()),
        "--mount",
        f"type=bind,src={output},dst=/work",
    ]
    inner = ["--project-root", "/project", "package", "--inside", "--output", "/work"]
    for name in ("stock_root", "reference", "bridge", "runtime", "seed"):
        source = checked_local(getattr(args, name), project_root)
        target = "/inputs/" + name
        command.extend(["--mount", f"type=bind,src={source},dst={target},readonly"])
        inner.extend(["--" + name.replace("_", "-"), target])
    run([*command, args.builder, *inner])
    return read_object(output / "package-manifest.json")


def _package_cache(output: Path, expected: dict[str, str]) -> dict[str, object]:
    """Check cache inputs and exact final-layer bytes without contacting Docker."""
    manifest = read_object(output / "package-manifest.json")
    if manifest.get("inputs") != expected:
        msg = "package inputs changed"
        raise ValueError(msg)
    if digest_file(output / "final-root.tar") != manifest["final_root_sha256"]:
        msg = "cached package changed"
        raise ValueError(msg)
    return manifest


def clean_failed_assembly(output: Path) -> None:
    """Remove only recognized generated products from a failed fresh assembly.

    The host must establish ownership and freshness before mounting this output.
    Success records, unknown members and symlinked roots refuse all deletion.
    Symlink children are unlinked without traversing their targets.
    """
    if output.is_symlink() or not output.is_dir():
        message = "failed assembly cleanup requires a real owned directory"
        raise ValueError(message)
    generated = {
        "tmp",
        "release.img",
        "fat",
        "partitions.json",
        "rufomaculata",
        "batocera",
        "root",
        "guestfs-cache",
        "stock-share.tar",
        "share-inventory-root",
        "share-manifest.json",
        "stock-manifest.json",
        "stock-root.tar",
        "builder-packages.tsv",
    }
    children = list(output.iterdir())
    if not {child.name for child in children} <= generated:
        message = "refusing cleanup of successful or unrecognized staging content"
        raise ValueError(message)
    for child in children:
        if child.is_symlink() or not child.is_dir():
            child.unlink()
        else:
            shutil.rmtree(child)


def main() -> None:
    """Parse explicit build roots and invoke installed assembly commands."""
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    root_parser.add_argument("--docker", default=os.environ.get("DOCKER", "docker"))
    root_args, remaining = root_parser.parse_known_args()
    parser = argparse.ArgumentParser(description=__doc__, parents=[root_parser])
    docker = shlex.split(root_args.docker)
    if not docker:
        parser.error("--docker requires a nonempty executable argv")
    project_root = root_args.project_root.resolve()
    # Docker selection belongs to host entry points. Builder execution never
    # imports host orchestration or its optional parser dependencies.
    if remaining and remaining[0] == "cleanup":
        cleanup = argparse.ArgumentParser(description=clean_failed_assembly.__doc__)
        cleanup.add_argument("--output", type=Path, required=True)
        cleanup.add_argument("--inside", action="store_true", required=True)
        cleanup_args = cleanup.parse_args(remaining[1:])
        clean_failed_assembly(cleanup_args.output)
        return
    if remaining and remaining[0] == "package":
        sys.stdout.write(
            json.dumps(
                package_command(
                    remaining[1:], project_root=project_root, docker=docker
                ),
                indent=2,
            )
            + "\n"
        )
        return
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--builder")
    parser.add_argument("--closure-bytes", type=int, default=0)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.closure_bytes < 0:
        parser.error("closure size must not be negative")
    if args.inside:
        if args.input_sha256 and digest_file(args.image) != args.input_sha256:
            msg = "verified input changed before isolated assembly"
            raise ValueError(msg)
        result = Assembler(
            args.image, args.output, args.closure_bytes, project_root=project_root
        ).assemble()
        if args.input_sha256:
            release = read_object(project_root / "build-assets/release.json")
            result.update(
                input_sha256=args.input_sha256,
                input_md5=release["compressed_md5"],
                release=release["release"],
                upstream_revision=release["upstream_revision"],
            )
            (Path(args.output) / "assembly-manifest.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
    else:
        if not args.builder:
            parser.error("--builder is required for isolated processing")
        result = assemble_in_builder(
            args.image,
            args.output,
            args.builder,
            args.closure_bytes,
            project_root=project_root,
            docker=docker,
        )
    sys.stdout.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
