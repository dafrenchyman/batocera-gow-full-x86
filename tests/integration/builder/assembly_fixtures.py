"""Create real GPT/FAT/ext4/zstd images in the networkless release builder."""

import argparse
import gzip
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from batocera_gow.builder.assemble import Assembler, extract_archive, package_root, run
from batocera_gow.builder.inventory import (
    Entry,
    Inventory,
    digest_file,
    read_snapshot,
    saved_image_layer,
    verify_image,
)
from batocera_gow.host.common import (
    ProjectPaths,
    docker_command,
    isolated_environment,
)
from batocera_gow.host.image import ImagePackager
from batocera_gow.provenance import project_mounts


def make_layers(directory: Path, *, collision: bool = False) -> Entry:
    """Create both complete roots with hardlinks and shared-directory metadata."""
    main, secondary = directory / "main", directory / "secondary"
    for root in (main, secondary):
        (root / "usr/share").mkdir(parents=True)
    (main / "boot").mkdir()
    (main / "usr/share/main-default.cfg").write_text(
        "official=true\n", encoding="utf-8"
    )
    (secondary / "usr/lib/libretro").mkdir(parents=True)
    (secondary / "usr/lib/libretro/secondary-core.so").write_bytes(
        b"secondary core\x00"
    )
    (secondary / "usr/share/wine").mkdir()
    (secondary / "usr/share/wine/secondary-only.dll").write_bytes(
        b"secondary wine asset"
    )
    (secondary / "absolute-link").symlink_to("/usr/share/wine")
    os.link(
        secondary / "usr/lib/libretro/secondary-core.so", secondary / "hardlinked-core"
    )
    if collision:
        (main / "usr/lib/libretro").mkdir(parents=True)
        (main / "usr/lib/libretro/secondary-core.so").write_bytes(b"must not override")
    shared = main / "usr/share"
    os.chown(shared, 123, 456)
    shared.chmod(0o750)
    run(
        [
            "setfattr",
            "-n",
            "user.gow-fixture",
            "-v",
            "preserved",
            main / "usr/share/main-default.cfg",
        ]
    )
    os.utime(shared, (1700000000, 1700000000))
    expected = Inventory(main).capture()["entries"]["/usr/share"]
    for source, name in ((main, "batocera"), (secondary, "rufomaculata")):
        run(
            [
                "mksquashfs",
                source,
                directory / name,
                "-noappend",
                "-comp",
                "zstd",
                "-processors",
                "1",
                "-quiet",
            ]
        )
    return expected


def make_disk(
    directory: Path, *, collision: bool = False, missing_secondary: bool = False
) -> tuple[Path, Entry]:
    """Create a real GPT disk with complete FAT and ACL-bearing ext4 SHARE."""
    directory.mkdir()
    expected = make_layers(directory, collision=collision)
    fat = directory / "fat-tree"
    (fat / "boot").mkdir(parents=True)
    (fat / "EFI/BOOT").mkdir(parents=True)
    for name in ("batocera", "rufomaculata"):
        if name != "rufomaculata" or not missing_secondary:
            shutil.copyfile(directory / name, fat / "boot" / name)
    (fat / "boot/linux").write_bytes(b"kernel fixture")
    (fat / "boot/initrd.gz").write_bytes(b"initramfs fixture")
    (fat / "EFI/BOOT/BOOTX64.EFI").write_bytes(b"EFI fixture")
    (fat / "batocera-boot.conf").write_text("stock boot config\n", encoding="utf-8")
    boot = directory / "boot.fat"
    with boot.open("wb") as stream:
        stream.truncate(64 * 1024 * 1024)
    run(["mkfs.vfat", "-F", "32", "-n", "BATOCERA", boot])
    for child in sorted(fat.iterdir()):
        run(["mcopy", "-s", "-i", boot, child, "::/"])
    seed = directory / "seed"
    seed.mkdir()
    (seed / "share-only-seed.cfg").write_text(
        "belongs to complete SHARE\n", encoding="utf-8"
    )
    run(["setfacl", "-m", "u:234:r--", seed / "share-only-seed.cfg"])
    (seed / "roms").mkdir()
    (seed / "roms/shipped-rom-note").write_text(
        "seed defaults retained separately\n", encoding="utf-8"
    )
    share = directory / "share.ext4"
    with share.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024)
    run(["mkfs.ext4", "-q", "-F", "-L", "SHARE", "-d", seed, share])
    disk = directory / "tiny.img"
    with disk.open("wb") as stream:
        stream.truncate(104 * 1024 * 1024)
    run(
        ["sfdisk", disk],
        stdin_text=(
            "label: gpt\nunit: sectors\n\n"
            "start=4096, size=131072, type=U\n"
            "start=135168, size=65536, type=L\n"
        ),
    )
    with disk.open("r+b") as destination:
        for partition_image, offset in ((boot, 4096 * 512), (share, 135168 * 512)):
            destination.seek(offset)
            with partition_image.open("rb") as stream:
                shutil.copyfileobj(stream, destination)
    compressed = directory / "tiny.img.gz"
    with (
        disk.open("rb") as source,
        gzip.open(compressed, "wb", compresslevel=1) as destination,
    ):
        shutil.copyfileobj(source, destination)
    return compressed, expected


def exercise(directory: Path, project_root: Path) -> None:
    """Exercise whole-root preservation and immutable additive packaging."""
    (directory / "tmp").mkdir(exist_ok=True)
    image, expected = make_disk(directory / "good-input")
    output = directory / "assembled"
    output.mkdir()
    result = Assembler(image, output, project_root=project_root).assemble()
    _verify_stock(directory, output, expected)
    _verify_package(directory, output, project_root)
    _verify_refusals(directory, project_root)
    sys.stdout.write(
        json.dumps(
            {
                "fixture": "complete GPT/FAT/ext4/zstd assembly",
                "stock_paths": result["stock_paths"],
                "result": "passed",
            }
        )
        + "\n"
    )


def _verify_stock(directory: Path, output: Path, expected: Entry) -> None:
    """Check both complete roots, FAT assets and separate SHARE metadata."""
    root = directory / "archive-root"
    root.mkdir()
    extract_archive(output / "stock-root.tar", root)
    actual = Inventory(root).capture()
    reference = read_snapshot(output / "stock-manifest.json")
    Inventory.compare(reference, actual)
    assert actual["entries"]["/usr/share"] == expected, (
        "main shared-directory metadata was lost"
    )
    assert (
        root / "usr/lib/libretro/secondary-core.so"
    ).read_bytes() == b"secondary core\x00"
    assert (
        root / "usr/share/wine/secondary-only.dll"
    ).read_bytes() == b"secondary wine asset"
    assert (root / "absolute-link").readlink() == Path("/usr/share/wine")
    assert (root / "hardlinked-core").stat().st_ino == (
        root / "usr/lib/libretro/secondary-core.so"
    ).stat().st_ino
    for name in (
        "boot/batocera",
        "boot/rufomaculata",
        "boot/linux",
        "boot/initrd.gz",
        "EFI/BOOT/BOOTX64.EFI",
        "batocera-boot.conf",
    ):
        assert (root / "boot" / name).is_file(), f"complete FAT asset absent: {name}"
    assert (
        "user.gow-fixture" in actual["entries"]["/usr/share/main-default.cfg"]["xattrs"]
    )
    seed = directory / "seed-root"
    seed.mkdir()
    extract_archive(output / "stock-share.tar", seed)
    assert (seed / "share-only-seed.cfg").read_text(
        encoding="utf-8"
    ) == "belongs to complete SHARE\n"
    assert (
        "system.posix_acl_access"
        in Inventory(seed).capture()["entries"]["/share-only-seed.cfg"]["xattrs"]
    )
    assert (seed / "roms/shipped-rom-note").is_file()
    Inventory.compare(
        read_snapshot(output / "share-manifest.json"),
        Inventory(seed).capture(),
    )


def _verify_package(directory: Path, output: Path, project_root: Path) -> None:
    """Exercise nested additive ownership hardening and exact stock preservation."""
    reference = read_snapshot(output / "stock-manifest.json")
    closure = directory / "closure"
    (closure / "nix/store/fixture-bridge/bin").mkdir(parents=True)
    (closure / "nix/store/fixture-bridge/bin/Xwayland").write_bytes(
        b"isolated closure fixture"
    )
    run(["tar", "-cf", directory / "bridge.tar", "-C", closure, "nix"])
    runtime = directory / "runtime"
    runtime.mkdir()
    (runtime / "entrypoint.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    os.chown(runtime, 1000, 1000)
    os.chown(runtime / "entrypoint.sh", 1000, 1000)
    runtime.chmod(0o777)
    (runtime / "entrypoint.sh").chmod(0o777)
    run(["setfacl", "-m", "u:1000:rwx,d:u:1000:rwx", runtime])
    run(["setfacl", "-m", "u:1000:rwx", runtime / "entrypoint.sh"])
    # Package-shaped hostile input exercises recursive module/asset hardening.
    module_directory = runtime / "batocera_gow/runtime"
    module_directory.mkdir(parents=True)
    (module_directory / "runtime.py").write_text(
        '"""Fixture runtime."""\n', encoding="utf-8"
    )
    (runtime / "alsa.conf").write_text("# fixture asset\n", encoding="utf-8")
    for path in [*runtime.rglob("*"), runtime]:
        os.chown(path, 1000, 1000)
        path.chmod(0o777)
        run(["setfacl", "-m", "u:1000:rwx", path])
    package = directory / "package"
    package.mkdir()
    package_root(
        output / "stock-root.tar",
        output / "stock-manifest.json",
        directory / "bridge.tar",
        runtime,
        output / "stock-share.tar",
        package,
        project_root=project_root,
    )
    packaged = directory / "packaged-root"
    packaged.mkdir()
    extract_archive(package / "final-root.tar", packaged)
    Inventory.compare(reference, Inventory(packaged).capture())
    assert (packaged / "opt/gow-full-x86/stock-share.tar").read_bytes() == (
        output / "stock-share.tar"
    ).read_bytes()
    for path in [
        packaged / "opt/gow-full-x86",
        *(packaged / "opt/gow-full-x86").rglob("*"),
    ]:
        info = path.stat()
        assert (info.st_uid, info.st_gid) == (0, 0), (
            "application owns privileged runtime code"
        )
        assert not stat.S_IMODE(info.st_mode) & 0o022, (
            "application can modify privileged runtime code"
        )
        assert not any(
            name.startswith("system.posix_acl_") for name in os.listxattr(path)
        ), "runtime inherited a writable ACL"
    (packaged / "usr/lib/libretro/secondary-core.so").unlink()
    with pytest.raises(ValueError, match="removed stock path"):
        Inventory.compare(reference, Inventory(packaged).capture())


def _verify_refusals(directory: Path, project_root: Path) -> None:
    """Missing roots and collisions cannot leave an assembly success record."""
    for name, options, expected_error in (
        ("collision", {"collision": True}, "non-directory collisions"),
        (
            "missing",
            {"missing_secondary": True},
            "required complete root layer missing",
        ),
    ):
        image, _ = make_disk(directory / (name + "-input"), **options)
        failed_output = directory / (name + "-output")
        failed_output.mkdir()
        with pytest.raises(ValueError, match=expected_error):
            Assembler(image, failed_output, project_root=project_root).assemble()
        assert not (failed_output / "assembly-manifest.json").exists()


def main() -> None:
    """Run real disposable builder assembly and exact Docker-load preservation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--inside", action="store_true")
    parser.add_argument(
        "--builder",
        default=os.environ.get(
            "GOW_FULL_X86_BUILDER", "batocera-gow-full-experiment-builder:trixie"
        ),
    )
    args = parser.parse_args()
    if args.inside:
        exercise(Path("/work"), args.project_root.resolve())
        return
    project_root = args.project_root.resolve()
    fixture = project_root / "tests/integration/builder/assembly_fixtures.py"
    output = project_root / "output/gow-full-x86/fixtures" / uuid.uuid4().hex
    output.mkdir(parents=True)

    docker = docker_command()
    run(
        [
            *docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--name",
            "batocera-gow-full-experiment-fixtures-" + uuid.uuid4().hex[:12],
            *project_mounts(project_root),
            "--mount",
            f"type=bind,src={fixture},dst=/fixtures/assembly_fixtures.py,readonly",
            "--mount",
            f"type=bind,src={output},dst=/work",
            "--entrypoint",
            "/opt/batocera-gow-tests/bin/python",
            args.builder,
            "/fixtures/assembly_fixtures.py",
            "--project-root",
            "/project",
            "--inside",
        ]
    )
    image = "batocera-gow-full-experiment-fixture:metadata-" + uuid.uuid4().hex
    try:
        ImagePackager(
            docker, project_root, isolated_environment(ProjectPaths(project_root))
        ).load(
            output / "package/final-root.tar",
            image,
            {"io.gow.full-x86.fixture": "true"},
        )
        # Compare the actual Docker-save layer bytes as well as every stock path.
        saved = output / "exact-image-save.tar"
        with saved.open("xb") as stream:
            # Configured Docker argv saves only this uniquely owned fixture image.
            subprocess.run(  # noqa: S603
                [*docker, "image", "save", image], stdout=stream, check=True
            )
        exact_layer = saved_image_layer(saved, output)
        assert digest_file(exact_layer) == digest_file(
            output / "package/final-root.tar"
        )
        verify_image(
            output / "assembled/stock-manifest.json",
            image,
            args.builder,
            output / "verification",
            project_root=project_root,
            docker=docker,
        )
    finally:
        run([*docker, "image", "rm", image])


if __name__ == "__main__":
    main()
