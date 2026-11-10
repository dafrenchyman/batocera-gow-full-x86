"""Check archive outcomes using local tools and explicit synthetic disk devices.

The disk tools below model external transcripts, not real SquashFS, GPT or
libguestfs acceptance. Tar, rsync, ACL removal and metadata capture use local
installed tools against disposable paths only.
"""

import gzip
import hashlib
import io
import json
import os
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypedDict, Unpack

import pytest

from batocera_gow.builder import assemble, inventory


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a complete independent set of declared build inputs."""
    root = tmp_path / "project"
    for directory in ("src/batocera_gow", "build-assets/runtime", "tests/assets"):
        (root / directory).mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".dockerignore",
        "LICENSE",
    ):
        (root / name).write_text("independent input\n", encoding="utf-8")
    (root / "src/batocera_gow/__init__.py").write_text("", encoding="utf-8")
    return root


def create_tar(source: Path, destination: Path) -> None:
    """Archive real metadata with the same host tar features used by packaging."""
    assemble.run(
        [
            "tar",
            "--create",
            "--file",
            destination,
            "--directory",
            source,
            "--format=posix",
            "--numeric-owner",
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--pax-option=delete=atime,delete=ctime",
            ".",
        ]
    )


def write_members(path: Path, members: list[tuple[str, bytes]]) -> None:
    """Write explicit archive bytes without extracting any member."""
    with tarfile.open(path, "w") as archive:
        for name, data in members:
            member = tarfile.TarInfo(name)
            member.uid, member.gid = os.getuid(), os.getgid()
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


@dataclass(frozen=True)
class PackageCase:
    """Keep independently owned package artifacts together for each case."""

    project: Path
    source: Path
    stock: Path
    reference: Path
    bridge: Path
    runtime: Path
    seed: Path
    output: Path

    def package(self) -> dict[str, object]:
        """Invoke the installed packaging operation with all explicit inputs."""
        return assemble.package_root(
            self.stock,
            self.reference,
            self.bridge,
            self.runtime,
            self.seed,
            self.output,
            project_root=self.project,
        )


@pytest.fixture
def package_case(project: Path) -> PackageCase:
    """Provide stock hardlinks, raw symlinks, closure and runtime as real archives."""
    source = project / "stock"
    (source / "usr/lib").mkdir(parents=True)
    (source / "opt").mkdir()
    program = source / "usr/lib/core.so"
    program.write_bytes(b"stock core\x00\xff")
    program.chmod(0o640)
    (source / "usr/lib/core-alias.so").hardlink_to(program)
    (source / "core-link").symlink_to("usr//lib/./core.so")
    (source / "stock-fifo").parent.mkdir(exist_ok=True)
    os.mkfifo(source / "stock-fifo", 0o600)
    for path in (source, *source.rglob("*")):
        os.utime(
            path,
            ns=(1_700_000_000_123456789, 1_700_000_000_123456789),
            follow_symlinks=False,
        )
    stock = project / "stock.tar"
    create_tar(source, stock)
    reference = project / "reference.json"
    reference.write_text(
        json.dumps(inventory.Inventory(source).capture()), encoding="utf-8"
    )
    bridge = project / "bridge.tar"
    write_members(bridge, [("nix/store/fixture/bin/tool", b"isolated closure")])
    runtime = project / "runtime"
    runtime.mkdir()
    (runtime / "launcher").write_bytes(b"runtime entrypoint\n")
    (runtime / "launcher").chmod(0o777)
    (runtime / "launcher-link").symlink_to("launcher")
    seed = project / "seed.tar"
    write_members(seed, [("system/settings", b"stock SHARE seed\n")])
    output = project / "package"
    output.mkdir()
    return PackageCase(project, source, stock, reference, bridge, runtime, seed, output)


def test_package_preserves_stock_and_embeds_only_isolated_additions(
    package_case: PackageCase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real final archive retains stock bytes, timestamps, modes and link groups."""
    case = package_case
    before = inventory.Inventory(case.source).capture()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble",
            "--project-root",
            str(case.project),
            "--docker",
            "synthetic-docker",
            "package",
            "--inside",
            "--stock-root",
            str(case.stock),
            "--reference",
            str(case.reference),
            "--bridge",
            str(case.bridge),
            "--runtime",
            str(case.runtime),
            "--seed",
            str(case.seed),
            "--output",
            str(case.output),
        ],
    )
    assemble.main()
    result = inventory.read_object(case.output / "package-manifest.json")
    assert json.loads(capsys.readouterr().out) == result
    assert result["verified_stock_paths"] == 8
    assert (
        result["final_root_sha256"]
        == hashlib.sha256((case.output / "final-root.tar").read_bytes()).hexdigest()
    )
    restored = case.project / "restored"
    restored.mkdir()
    assemble.extract_archive(case.output / "final-root.tar", restored)
    captured = inventory.Inventory(restored).capture()
    for name, entry in before["entries"].items():
        assert captured["entries"][name] == entry
    assert (restored / "nix/store/fixture/bin/tool").read_bytes() == b"isolated closure"
    assert (
        restored / "opt/gow-full-x86/launcher"
    ).read_bytes() == b"runtime entrypoint\n"
    assert (restored / "opt/gow-full-x86/launcher").stat().st_mode & 0o777 == 0o755
    assert (restored / "opt/gow-full-x86/launcher-link").readlink() == Path("launcher")
    assert (
        restored / "opt/gow-full-x86/stock-share.tar"
    ).read_bytes() == case.seed.read_bytes()
    assert (
        restored / "opt/gow-full-x86/stock-share.tar"
    ).stat().st_mode & 0o777 == 0o644
    assert inventory.Inventory(case.source).capture() == before
    assert sorted(path.name for path in case.output.iterdir()) == [
        "final-root.tar",
        "package-manifest.json",
    ]
    assert inventory.read_object(case.output / "package-manifest.json") == result


@pytest.mark.parametrize(
    "name", ["usr", "opt/gow-full-x86/injected", "./nix/store/tool"]
)
def test_package_refuses_closure_outside_exact_store_namespace(
    package_case: PackageCase,
    name: str,
) -> None:
    """A closure cannot overwrite stock metadata or smuggle a runtime addition."""
    case = package_case
    write_members(case.bridge, [(name, b"untrusted closure")])
    with pytest.raises(ValueError, match="closure path outside /nix/store"):
        case.package()
    assert not (case.output / "package-manifest.json").exists()
    assert not (case.output / "final-root.tar").exists()
    assert (case.source / "usr/lib/core.so").read_bytes() == b"stock core\x00\xff"
    assert not (case.output / "root/opt/gow-full-x86").exists()


def test_package_refuses_corrupt_stock_before_installing_runtime(
    package_case: PackageCase,
) -> None:
    """A valid archive with wrong stock bytes still cannot become a success record."""
    case = package_case
    write_members(case.stock, [("usr/lib/core.so", b"altered core")])
    with pytest.raises(ValueError, match=r"changed stock path|removed stock path"):
        case.package()
    assert not (case.output / "root/nix").exists()
    assert not (case.output / "package-manifest.json").exists()
    assert not (case.output / "final-root.tar").exists()


def test_package_refuses_nonfresh_output_without_touching_operator_content(
    package_case: PackageCase,
) -> None:
    """Freshness refusal happens before any extraction or deletion."""
    sentinel = package_case.output / "operator-save"
    sentinel.write_bytes(b"retain")
    with pytest.raises(ValueError, match="packaging output must be fresh"):
        package_case.package()
    assert list(package_case.output.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"retain"


def test_package_input_drift_prevents_success_record(
    package_case: PackageCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A boundary-side edit during final archive creation invalidates promotion."""
    original = assemble.run

    def mutate_after_tar(
        command: Sequence[str | Path],
        *,
        stdin_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        result = original(command, stdin_text=stdin_text, env=env)
        if package_case.output / "final-root.tar" in command:
            (package_case.runtime / "launcher").write_bytes(b"changed during packaging")
        return result

    monkeypatch.setattr(assemble, "run", mutate_after_tar)
    with pytest.raises(ValueError, match="package inputs changed during assembly"):
        package_case.package()
    assert (package_case.output / "final-root.tar").is_file()
    assert not (package_case.output / "package-manifest.json").exists()
    assert (
        package_case.output / "root/usr/lib/core.so"
    ).read_bytes() == b"stock core\x00\xff"


class SpawnOptions(TypedDict, total=False):
    """Describe the subprocess options accepted by the synthetic disk reader."""

    stdout: int | None
    stderr: int | None
    stdin: int | None
    text: bool
    env: Mapping[str, str] | None


@dataclass
class DiskTools:
    """Model only external disk readers, delegating archive/copy work to host tools."""

    boot: Path
    secondary: Path
    main: Path
    share: Path
    filesystem: str = "ext4"
    listing_status: int = 0

    def read(
        self,
        command: Sequence[str],
        *,
        text: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> str:
        """Return a two-partition device transcript or its selected filesystem."""
        del text, env
        if command[0] == "/usr/sbin/sfdisk":
            return json.dumps(
                {
                    "partitiontable": {
                        "label": "gpt",
                        "unit": "sectors",
                        "sectorsize": 512,
                        "firstlba": 1,
                        "lastlba": 14,
                        "partitions": [
                            {
                                "start": 2,
                                "size": 4,
                                "type": assemble.EFI_TYPE,
                                "name": "BOOT",
                            },
                            {
                                "start": 6,
                                "size": 8,
                                "type": assemble.LINUX_TYPE,
                                "name": "SHARE",
                            },
                        ],
                    }
                }
            )
        if command[0] == "/usr/sbin/blkid":
            return (
                "vfat\n"
                if command[command.index("-O") + 1] == "1024"
                else self.filesystem + "\n"
            )
        if command[0] == "/usr/bin/guestfish":
            return self.filesystem + "\n"
        raise AssertionError(command)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Install bounded process transcripts, preserving real tar and rsync."""
        original_run, original_popen = assemble.run, subprocess.Popen

        def run(
            command: Sequence[str | Path],
            *,
            stdin_text: str | None = None,
            env: Mapping[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            argv = [str(item) for item in command]
            if argv[0] == "mcopy":
                shutil.copytree(
                    self.boot, Path(argv[-1]), dirs_exist_ok=True, symlinks=True
                )
            elif argv[0] == "unsquashfs":
                source = (
                    self.secondary
                    if Path(argv[-1]).name == "rufomaculata"
                    else self.main
                )
                shutil.copytree(source, Path(argv[argv.index("-d") + 1]), symlinks=True)
            elif argv[0] == "guestfish":
                destination = Path(argv[argv.index("tar-out") + 2])
                original_run(
                    [
                        "tar",
                        "--create",
                        "--file",
                        destination,
                        "--directory",
                        self.share,
                        "--format=posix",
                        "--numeric-owner",
                        "--xattrs",
                        "--xattrs-include=*",
                        ".",
                    ]
                )
            else:
                return original_run(command, stdin_text=stdin_text, env=env)
            return subprocess.CompletedProcess(argv, 0, "", "")

        def spawn(
            command: Sequence[str],
            **options: Unpack[SpawnOptions],
        ) -> subprocess.Popen[str]:
            argv = list(command)
            if argv[0] == "/usr/bin/unsquashfs":
                argv = [
                    sys.executable,
                    "-c",
                    (
                        "import sys; print('Parallel unsquashfs'); "
                        "print('-rw-r--r-- 0/0 37 2026-01-01 00:00 "
                        "squashfs-root/core'); "
                        "print('drwxr-xr-x 0/0 0 2026-01-01 00:00 squashfs-root'); "
                        f"sys.exit({self.listing_status})"
                    ),
                ]
            return original_popen(
                argv,
                stdout=options.get("stdout"),
                stderr=options.get("stderr"),
                stdin=options.get("stdin"),
                text=True,
                env=options.get("env"),
            )

        monkeypatch.setattr(subprocess, "check_output", self.read)
        monkeypatch.setattr(subprocess, "Popen", spawn)
        monkeypatch.setattr(assemble, "run", run)


@pytest.fixture
def disk_case(project: Path) -> tuple[assemble.Assembler, DiskTools]:
    """Prepare tiny compressed disk bytes and independent external-tool trees."""
    fixture = project / "devices"
    boot, secondary, main, share = [
        fixture / name for name in ("fat", "secondary", "main", "share")
    ]
    for path in (
        boot / "boot",
        secondary / "usr/lib",
        main / "usr/bin",
        share / "system",
    ):
        path.mkdir(parents=True)
    for name in ("batocera", "rufomaculata"):
        block = bytearray(128)
        block[:4] = b"hsqs"
        struct.pack_into("<I", block, 4, 2)
        struct.pack_into("<H", block, 28, 4)
        struct.pack_into("<Q", block, 40, 128)
        (boot / "boot" / name).write_bytes(block)
    (boot / "firmware.cfg").write_bytes(b"complete FAT extra")
    (secondary / "usr/lib/secondary.so").write_bytes(b"secondary layer")
    (main / "usr/bin/frontend").write_bytes(b"main layer")
    (main / "usr/bin/frontend").chmod(0o751)
    (main / "absolute-link").symlink_to("/usr/bin/frontend")
    (share / "system/settings").write_bytes(b"stock SHARE configuration")
    image = project / "release.img.gz"
    with gzip.open(image, "wb") as stream:
        stream.write(b"synthetic disk".ljust(8192, b"\x00"))
    output = project / "assembly"
    output.mkdir()
    return assemble.Assembler(image, output, 13, project_root=project), DiskTools(
        boot, secondary, main, share
    )


def test_assembly_exports_all_layers_boot_and_share_then_cleans_owned_products(
    disk_case: tuple[assemble.Assembler, DiskTools],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Synthetic disk readers still produce independently inspected real archives."""
    builder, tools = disk_case
    tools.install(monkeypatch)
    compressed = builder.image.read_bytes()
    release = builder.project_root / "build-assets/release.json"
    release.write_text(
        json.dumps(
            {
                "compressed_md5": hashlib.md5(
                    compressed, usedforsecurity=False
                ).hexdigest(),
                "release": "fixture-release",
                "upstream_revision": "fixture-revision",
            }
        ),
        encoding="utf-8",
    )
    input_sha = hashlib.sha256(compressed).hexdigest()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "assemble",
            "--project-root",
            str(builder.project_root),
            "--docker",
            "synthetic-docker",
            "--inside",
            "--image",
            str(builder.image),
            "--output",
            str(builder.output),
            "--input-sha256",
            input_sha,
            "--closure-bytes",
            "13",
        ],
    )
    assemble.main()
    result = inventory.read_object(builder.output / "assembly-manifest.json")
    assert json.loads(capsys.readouterr().out) == result
    assert result["input_sha256"] == input_sha
    assert result["release"] == "fixture-release"
    assert result["upstream_revision"] == "fixture-revision"
    assert result["disk_bytes"] == 8192
    assert result["remaining_space_bound_bytes"] == 176537
    assert result["closure_bytes"] == 13
    stock = inventory.read_snapshot(builder.output / "stock-manifest.json")
    assert stock["entries"]["/usr/bin/frontend"]["mode"] == 0o751
    assert stock["entries"]["/absolute-link"].get("target") == "/usr/bin/frontend"
    assert stock["entries"]["/boot/firmware.cfg"].get("size") == 18
    with tarfile.open(builder.output / "stock-root.tar") as archive:
        for name, expected in (
            ("./usr/lib/secondary.so", b"secondary layer"),
            ("./usr/bin/frontend", b"main layer"),
            ("./boot/firmware.cfg", b"complete FAT extra"),
        ):
            stream = archive.extractfile(name)
            assert stream is not None
            with stream:
                assert stream.read() == expected
    share = inventory.read_snapshot(builder.output / "share-manifest.json")
    assert share["entries"]["/system/settings"].get("size") == 25
    assert builder.image.read_bytes() == compressed
    assert not builder.disk.exists()
    for name in (
        "root",
        "fat",
        "batocera",
        "rufomaculata",
        "tmp",
        "guestfs-cache",
        "share-inventory-root",
    ):
        assert not (builder.output / name).exists()
    assert inventory.read_object(builder.output / "assembly-manifest.json") == result
    reused = assemble.assemble_in_builder(
        builder.image,
        builder.output,
        "new-tools-selector",
        13,
        project_root=builder.project_root,
        docker=["must-not-execute"],
    )
    assert reused["builder"] == "new-tools-selector"
    assert reused["stock_root_sha256"] == result["stock_root_sha256"]
    assert inventory.read_object(builder.output / "assembly-manifest.json") == result


@pytest.mark.parametrize(
    "kind", ["file-collision", "reserved-nix", "bad-opt", "bad-boot", "nonempty-boot"]
)
def test_assembly_refuses_stock_collisions_without_exporting_success(
    disk_case: tuple[assemble.Assembler, DiskTools],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """Overlaps and unsafe addition/mount roots cannot produce a stock archive."""
    builder, tools = disk_case
    if kind == "file-collision":
        (tools.main / "usr/lib").mkdir()
        (tools.main / "usr/lib/secondary.so").write_bytes(b"conflicting main")
    elif kind == "reserved-nix":
        (tools.main / "nix").symlink_to("/foreign")
    elif kind == "bad-opt":
        (tools.main / "opt").write_bytes(b"not a directory")
    elif kind == "bad-boot":
        (tools.main / "boot").symlink_to("/foreign")
    else:
        (tools.main / "boot").mkdir()
        (tools.main / "boot/foreign").write_bytes(b"must not merge")
    tools.install(monkeypatch)
    with pytest.raises(
        ValueError,
        match=r"collisions|collides|not a real directory|not an empty mountpoint",
    ):
        builder.assemble()
    assert not (builder.output / "assembly-manifest.json").exists()
    assert not (builder.output / "stock-root.tar").exists()
    assert builder.image.is_file()
    assemble.clean_failed_assembly(builder.output)
    assert list(builder.output.iterdir()) == []
    assert builder.image.is_file()


@pytest.mark.parametrize(
    "failure", ["missing-layer", "wrong-filesystem", "listing-failure", "input-drift"]
)
def test_assembly_failure_retains_verified_input_and_never_commits_manifest(
    disk_case: tuple[assemble.Assembler, DiskTools],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """External-reader errors and source drift cannot leave reusable successes."""
    builder, tools = disk_case
    if failure == "missing-layer":
        (tools.boot / "boot/rufomaculata").unlink()
    elif failure == "wrong-filesystem":
        tools.filesystem = "xfs"
    elif failure == "listing-failure":
        tools.listing_status = 7
    else:
        (tools.main / "usr/bin/frontend").write_bytes(b"main layer")
    tools.install(monkeypatch)
    if failure == "input-drift":
        original = assemble.run

        def drift(
            command: Sequence[str | Path],
            *,
            stdin_text: str | None = None,
            env: Mapping[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            result = original(command, stdin_text=stdin_text, env=env)
            if builder.output / "stock-root.tar" in command:
                (builder.project_root / "uv.lock").write_text(
                    "changed\n", encoding="utf-8"
                )
            return result

        monkeypatch.setattr(assemble, "run", drift)
    with pytest.raises(
        ValueError,
        match=(
            r"root layer missing|expected ext4|"
            r"cannot list complete SquashFS|inputs changed"
        ),
    ):
        builder.assemble()
    assert not (builder.output / "assembly-manifest.json").exists()
    assert builder.image.is_file()
    assemble.clean_failed_assembly(builder.output)
    assert list(builder.output.iterdir()) == []


def test_empty_compressed_disk_cannot_allocate_extracted_products(
    project: Path,
) -> None:
    """A valid empty gzip stream is refused before any disk output is allocated."""
    image = project / "empty.gz"
    with gzip.open(image, "wb"):
        pass
    output = project / "empty-output"
    output.mkdir()
    builder = assemble.Assembler(image, output, project_root=project)
    with pytest.raises(ValueError, match="empty compressed disk image"):
        builder.decompressed_size()
    assert list(output.iterdir()) == []


def test_inventory_capture_refuses_live_socket_without_following_it(
    tmp_path: Path,
) -> None:
    """Live IPC endpoints cannot silently disappear from complete stock archives."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as endpoint:
        endpoint.bind(str(tmp_path / "live.sock"))
        with pytest.raises(
            ValueError, match=r"cannot archive a live socket: /live\.sock"
        ):
            inventory.Inventory(tmp_path).capture()
        assert stat.S_ISSOCK((tmp_path / "live.sock").lstat().st_mode)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", True),
        ("uid", "0"),
        ("xattrs", {"user.bad": 7}),
        ("hardlinks", "/not-a-list"),
        ("device", "1:3"),
        ("extra", 1),
    ],
)
def test_inventory_serialization_refuses_ambiguous_metadata(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    """Malformed metadata is refused before ownership, link or content comparison."""
    document: dict[str, object] = {
        "type": 32768,
        "mode": 420,
        "uid": 0,
        "gid": 0,
        "mtime_ns": 123,
        "xattrs": {},
        "size": 3,
        "sha256": "digest",
    }
    document[field] = value
    reference = tmp_path / "reference.json"
    reference.write_text(
        json.dumps({"schema": 1, "entries": {"/file": document}}), encoding="utf-8"
    )
    with pytest.raises(
        ValueError,
        match=(
            r"expected an integer|expected a string|invalid hardlink|"
            r"invalid device|unsupported inventory fields"
        ),
    ):
        inventory.read_snapshot(reference)


@pytest.mark.parametrize("name", ["/opt", "/nix", "/nix/store", "/opt/gow-full-x86"])
def test_inventory_refuses_symlink_as_allowed_addition_parent(
    tmp_path: Path, name: str
) -> None:
    """An allowed namespace does not permit replacing its parent with a link."""
    reference = inventory.Inventory(tmp_path).capture()
    candidate = inventory.Inventory(tmp_path).capture()
    candidate["entries"][name] = {
        "type": stat.S_IFLNK,
        "mode": 0o777,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "mtime_ns": 0,
        "xattrs": {},
        "target": "/foreign",
    }
    with pytest.raises(ValueError, match="addition parent is not a directory"):
        inventory.Inventory.compare(reference, candidate)


def test_inventory_rejects_hardlink_to_directory_before_extraction(
    tmp_path: Path,
) -> None:
    """A syntactically contained link must still identify an archived file."""
    archive = tmp_path / "bad-link.tar"
    with tarfile.open(archive, "w") as stream:
        directory = tarfile.TarInfo("directory")
        directory.type = tarfile.DIRTYPE
        stream.addfile(directory)
        link = tarfile.TarInfo("link")
        link.type, link.linkname = tarfile.LNKTYPE, "directory"
        stream.addfile(link)
    with pytest.raises(ValueError, match="hardlink does not name a file"):
        inventory.validate_tar(archive)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bad-link.tar"]


def test_saved_layer_refuses_nonregular_member_before_creating_copy(
    tmp_path: Path,
) -> None:
    """A Docker manifest cannot select a symlink as its flattened layer."""
    archive = tmp_path / "saved.tar"
    with tarfile.open(archive, "w") as stream:
        data = b'[{"Layers":["layer.tar"]}]'
        manifest = tarfile.TarInfo("manifest.json")
        manifest.size = len(data)
        stream.addfile(manifest, io.BytesIO(data))
        layer = tarfile.TarInfo("layer.tar")
        layer.type, layer.linkname = tarfile.SYMTYPE, "other.tar"
        stream.addfile(layer)
    with pytest.raises(ValueError, match="not a regular file"):
        inventory.saved_image_layer(archive, tmp_path)
    assert not (tmp_path / "filesystem-layer.tar").exists()


@dataclass(frozen=True)
class AvailableStorage:
    """Expose only the storage observation used at the allocation boundary."""

    total: int = 1024
    used: int = 1023
    free: int = 1


def test_assembly_storage_refusal_preserves_compressed_input(
    disk_case: tuple[assemble.Assembler, DiskTools],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capacity refusal cannot create a decompressed disk or destroy its input."""
    builder, _tools = disk_case
    compressed = builder.image.read_bytes()

    def constrained(_path: Path) -> AvailableStorage:
        return AvailableStorage()

    monkeypatch.setattr(shutil, "disk_usage", constrained)
    with pytest.raises(
        ValueError, match=r"insufficient storage.*verified input retained"
    ):
        builder.unpack_disk(8192)
    assert builder.image.read_bytes() == compressed
    assert list(builder.output.iterdir()) == []


def test_saved_layer_storage_refusal_cannot_leave_a_partial_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The space bound is checked before opening the sole layer destination."""
    archive = tmp_path / "saved.tar"
    write_members(
        archive,
        [
            ("manifest.json", b'[{"Layers":["layer.tar"]}]'),
            ("layer.tar", b"complete layer stream"),
        ],
    )
    original = archive.read_bytes()

    def constrained(_path: Path) -> AvailableStorage:
        return AvailableStorage()

    monkeypatch.setattr(shutil, "disk_usage", constrained)
    with pytest.raises(ValueError, match="at least 42 additional bytes"):
        inventory.saved_image_layer(archive, tmp_path)
    assert not (tmp_path / "filesystem-layer.tar").exists()
    assert archive.read_bytes() == original


@dataclass
class ImageTransport:
    """Supply a synthetic Docker-save transport, never a real daemon or image."""

    saved: Path
    output: Path
    reference: Path
    monkeypatch: pytest.MonkeyPatch

    def install(self) -> None:
        """Run installed verification using real host tar at the process boundary.

        The builder uses /usr/bin/tar. Resolving the host tar here deliberately
        establishes host archive behavior only, not a provisioned builder claim.
        """
        original = subprocess.run
        host_tar = shutil.which("tar")
        assert host_tar is not None

        def run(
            command: Sequence[str],
            *,
            stdout: BinaryIO | None = None,
            check: bool = False,
        ) -> subprocess.CompletedProcess[str]:
            argv = list(command)
            if argv[0] == "/usr/bin/tar":
                return original(
                    [host_tar, *argv[1:]], stdout=stdout, check=check, text=True
                )
            assert argv[0] == "synthetic-docker"
            if argv[1:3] == ["image", "save"]:
                assert stdout is not None
                with self.saved.open("rb") as source:
                    shutil.copyfileobj(source, stdout)
                return subprocess.CompletedProcess(argv, 0)
            assert argv[1] == "run"
            # Translation is confined to this external container boundary.
            with self.monkeypatch.context() as context:
                context.setattr(
                    sys,
                    "argv",
                    [
                        "inventory",
                        "unpack-verify",
                        "--archive",
                        str(self.output / "image-save.tar"),
                        "--saved-image",
                        "--reference",
                        str(self.reference),
                        "--output",
                        str(self.output),
                    ],
                )
                inventory.main()
            return subprocess.CompletedProcess(argv, 0)

        self.monkeypatch.setattr(subprocess, "run", run)


@pytest.mark.parametrize("changed", [False, True])
def test_image_verification_compares_real_layer_and_cleans_only_after_success(
    package_case: PackageCase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    changed: bool,
) -> None:
    """The save boundary must compare bytes and metadata, not trust its manifest."""
    case = package_case
    if changed:
        (case.source / "usr/lib/core.so").write_bytes(b"unexpected stock replacement")
        create_tar(case.source, case.stock)
    saved = case.project / "saved-fixture.tar"
    write_members(
        saved,
        [
            ("manifest.json", b'[{"Layers":["layer.tar"]}]'),
            ("layer.tar", case.stock.read_bytes()),
        ],
    )
    output = case.project / "verification"
    transport = ImageTransport(saved, output, case.reference, monkeypatch)
    transport.install()
    if changed:
        with pytest.raises(ValueError, match="changed stock path: /usr/lib/core"):
            inventory.verify_image(
                case.reference,
                "fixture-image",
                "fixture-builder",
                output,
                project_root=case.project,
                docker=["synthetic-docker"],
            )
        assert not (output / "inventory-verification.json").exists()
        assert (output / "image-save.tar").is_file()
        assert (output / "filesystem-layer.tar").is_file()
        assert (
            output / "unpacked/usr/lib/core.so"
        ).read_bytes() == b"unexpected stock replacement"
    else:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "inventory",
                "--project-root",
                str(case.project),
                "verify",
                "--reference",
                str(case.reference),
                "--image",
                "fixture-image",
                "--builder",
                "fixture-builder",
                "--output",
                str(output),
                "--docker",
                "synthetic-docker",
            ],
        )
        inventory.main()
        result = json.loads(capsys.readouterr().out)
        assert result == {
            "verified_stock_paths": 8,
            "added_paths": 0,
            "image": "fixture-image",
        }
        assert inventory.read_object(output / "inventory-verification.json") == {
            "verified_stock_paths": 8,
            "added_paths": 0,
        }
        assert not (output / "unpacked").exists()
        assert not (output / "filesystem-layer.tar").exists()
        assert not (output / "image-save.tar").exists()
    assert saved.is_file()
    assert case.reference.is_file()
    assert (case.source / "core-link").is_symlink()


def test_image_save_process_failure_preserves_partial_evidence_without_success(
    project: Path,
) -> None:
    """A failing external save cannot advance to image extraction or comparison."""
    reference = project / "reference.json"
    reference.write_text('{"schema":1,"entries":{}}', encoding="utf-8")
    output = project / "failed-verification"
    with pytest.raises(subprocess.CalledProcessError) as error:
        inventory.verify_image(
            reference,
            "fixture-image",
            "must-not-run",
            output,
            project_root=project,
            docker=[
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'partial save'); sys.exit(9)",
            ],
        )
    assert error.value.returncode == 9
    assert (output / "image-save.tar").read_bytes() == b"partial save"
    assert not (output / "unpacked").exists()
    assert not (output / "inventory-verification.json").exists()


def test_image_verification_refuses_nonfresh_output_before_saving(
    project: Path,
) -> None:
    """Verification will not overwrite prior evidence or contact an external tool."""
    reference = project / "reference.json"
    reference.write_text("{}", encoding="utf-8")
    output = project / "verification"
    output.mkdir()
    sentinel = output / "inventory-verification.json"
    sentinel.write_bytes(b"previous evidence")
    with pytest.raises(ValueError, match="verification output must be fresh"):
        inventory.verify_image(
            reference,
            "fixture-image",
            "fixture-builder",
            output,
            project_root=project,
            docker=["must-not-execute"],
        )
    assert list(output.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"previous evidence"


@pytest.mark.parametrize("escape", ["root", "outside", "symlink"])
def test_image_verification_refuses_unowned_destinations(
    project: Path,
    tmp_path: Path,
    escape: str,
) -> None:
    """Canonical containment is required before any archive or directory write."""
    reference = project / "reference.json"
    reference.write_text("{}", encoding="utf-8")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    if escape == "root":
        output = project
    elif escape == "outside":
        output = foreign / "verification"
    else:
        output = project / "escape"
        output.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="path escapes independent project"):
        inventory.verify_image(
            reference,
            "fixture-image",
            "fixture-builder",
            output,
            project_root=project,
            docker=["must-not-execute"],
        )
    assert list(foreign.iterdir()) == []
    assert not (project / "image-save.tar").exists()


def test_inventory_capture_command_serializes_real_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capture produces a portable reference without changing its source tree."""
    root = tmp_path / "stock"
    root.mkdir()
    (root / "program").write_bytes(b"abc")
    (root / "program").chmod(0o751)
    (root / "alias").hardlink_to(root / "program")
    (root / "link").symlink_to("/program")
    output = tmp_path / "captured.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "inventory",
            "capture",
            "--root",
            str(root),
            "--output",
            str(output),
        ],
    )
    inventory.main()
    snapshot = inventory.read_snapshot(output)
    assert snapshot["entries"]["/program"].get("sha256") == (
        # pragma: allowlist nextline secret
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert snapshot["entries"]["/program"]["mode"] == 0o751
    assert snapshot["entries"]["/program"].get("hardlinks") == ["/alias", "/program"]
    assert snapshot["entries"]["/link"].get("target") == "/program"
    assert (root / "alias").stat().st_ino == (root / "program").stat().st_ino
