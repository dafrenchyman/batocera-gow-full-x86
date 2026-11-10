"""Exercise safe scans, archive headers and complete installed-input cache identity."""

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.builder import assemble
from batocera_gow.builder.inventory import digest_file


def test_scan_never_follows_absolute_stock_symlinks(tmp_path: Path) -> None:
    """A root symlink is inventoried without scanning the host filesystem."""
    (tmp_path / "root-link").symlink_to("/")
    assert assemble.walk_types(tmp_path) == {"root-link": False}


def test_squashfs_superblock_size_is_validated(tmp_path: Path) -> None:
    """The declared used length must fit inside the real SquashFS image."""
    path = tmp_path / "layer"
    data = bytearray(128)
    data[:4] = b"hsqs"
    struct.pack_into("<I", data, 4, 7)
    struct.pack_into("<H", data, 28, 4)
    struct.pack_into("<Q", data, 40, 100)
    path.write_bytes(data)
    assert assemble.squashfs_superblock(path) == {"bytes_used": 100, "inode_count": 7}
    struct.pack_into("<Q", data, 40, 1000)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="invalid SquashFS superblock"):
        assemble.squashfs_superblock(path)


@pytest.fixture
def declared_project(tmp_path: Path) -> Path:
    """Provide all declared inputs in an independent checkout-like directory."""
    root = tmp_path / "project"
    for name in ("src/batocera_gow/builder", "build-assets/runtime", "tests/assets"):
        (root / name).mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".dockerignore",
        "LICENSE",
        "src/batocera_gow/builder/assemble.py",
        "build-assets/runtime/alsa.conf",
        "tests/assets/cases.json",
    ):
        (root / name).write_text("fixture input\n", encoding="utf-8")
    return root


def test_assembly_cache_requires_matching_provenance_and_artifacts(
    tmp_path: Path, declared_project: Path
) -> None:
    """Valid reuse retains bytes; input changes and corruption refuse reuse."""
    output = tmp_path / "assembly"
    output.mkdir()
    manifest: dict[str, object] = {
        "input_sha256": "verified-input",
        "closure_bytes": 17,
        "assembly_source_sha256": assemble.source_fingerprint(declared_project),
    }
    for name, key in (
        ("stock-root.tar", "stock_root_sha256"),
        ("stock-share.tar", "stock_share_sha256"),
        ("stock-manifest.json", "stock_manifest_sha256"),
        ("share-manifest.json", "share_manifest_sha256"),
    ):
        (output / name).write_bytes(name.encode())
        manifest[key] = digest_file(output / name)
    (output / "assembly-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    assert (
        assemble.cached_assembly(
            output, "verified-input", 17, project_root=declared_project
        )
        == manifest
    )
    with pytest.raises(ValueError, match="fresh --output"):
        assemble.cached_assembly(
            output, "other-input", 17, project_root=declared_project
        )
    (output / "stock-root.tar").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="fresh --output"):
        assemble.cached_assembly(
            output, "verified-input", 17, project_root=declared_project
        )


@pytest.mark.parametrize(
    "name",
    [
        "src/batocera_gow/builder/assemble.py",
        "build-assets/runtime/alsa.conf",
        "tests/assets/cases.json",
        "uv.lock",
        ".python-version",
        "pyproject.toml",
        ".dockerignore",
    ],
)
def test_consumed_input_mutation_invalidates_fingerprint(
    declared_project: Path, name: str
) -> None:
    """Transitive code, assets and dependency/interpreter inputs affect caches."""
    before = assemble.source_fingerprint(declared_project)
    (declared_project / name).write_text("changed input\n", encoding="utf-8")
    assert assemble.source_fingerprint(declared_project) != before


def test_mode_addition_and_bytecode_cache_identity(declared_project: Path) -> None:
    """Modes and new helpers invalidate identity while bytecode stays ignored."""
    path = declared_project / "src/batocera_gow/builder/assemble.py"
    before = assemble.source_fingerprint(declared_project)
    path.chmod(path.stat().st_mode ^ 0o100)
    assert assemble.source_fingerprint(declared_project) != before
    before = assemble.source_fingerprint(declared_project)
    (path.parent / "new_helper.py").write_text("helper\n", encoding="utf-8")
    assert assemble.source_fingerprint(declared_project) != before
    before = assemble.source_fingerprint(declared_project)
    cache = path.parent / "__pycache__"
    cache.mkdir()
    (cache / "helper.pyc").write_bytes(b"ignored")
    assert assemble.source_fingerprint(declared_project) == before


def test_failed_assembly_cleanup_retains_unknown_and_successful_output(
    tmp_path: Path,
) -> None:
    """Cleanup validates the whole directory before deleting any product."""
    (tmp_path / "release.img").write_bytes(b"disposable")
    success = tmp_path / "assembly-manifest.json"
    success.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized"):
        assemble.clean_failed_assembly(tmp_path)
    assert (tmp_path / "release.img").read_bytes() == b"disposable"
    success.unlink()
    (tmp_path / "operator-data").write_bytes(b"retain")
    with pytest.raises(ValueError, match="unrecognized"):
        assemble.clean_failed_assembly(tmp_path)
    assert (tmp_path / "release.img").exists()


def test_failed_assembly_cleanup_never_follows_symlinks(tmp_path: Path) -> None:
    """Generated symlink names are removed without touching foreign targets."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "content").write_bytes(b"protected")
    output = tmp_path / "failed"
    output.mkdir()
    (output / "root").symlink_to(foreign, target_is_directory=True)
    (output / "tmp").mkdir()
    (output / "tmp/partial").write_bytes(b"discard")
    assemble.clean_failed_assembly(output)
    assert list(output.iterdir()) == []
    assert (foreign / "content").read_bytes() == b"protected"
    root_link = tmp_path / "root-link"
    root_link.symlink_to(output, target_is_directory=True)
    with pytest.raises(ValueError, match="real owned directory"):
        assemble.clean_failed_assembly(root_link)


def test_package_cache_checks_transitive_inputs_and_archive_integrity(
    declared_project: Path,
) -> None:
    """An intact cached package is reused; changed assets or tar bytes refuse."""
    inputs = declared_project / "output/inputs"
    inputs.mkdir(parents=True)
    paths = [
        inputs / name
        for name in ("stock.tar", "reference.json", "bridge.tar", "seed.tar")
    ]
    for path in paths:
        path.write_bytes(path.name.encode())
    stock, reference, bridge, seed = paths
    runtime = inputs / "runtime"
    runtime.mkdir()
    executable = runtime / "launcher.sh"
    executable.write_text("true\n", encoding="utf-8")
    expected = assemble.package_inputs(
        stock, reference, bridge, runtime, seed, project_root=declared_project
    )
    os.utime(executable, ns=(42, 42))
    assert (
        assemble.package_inputs(
            stock, reference, bridge, runtime, seed, project_root=declared_project
        )
        == expected
    )
    executable.chmod(executable.stat().st_mode ^ 0o100)
    assert (
        assemble.package_inputs(
            stock, reference, bridge, runtime, seed, project_root=declared_project
        )
        != expected
    )
    output = declared_project / "output/package"
    output.mkdir()
    archive = output / "final-root.tar"
    archive.write_bytes(b"complete exact layer")
    manifest: dict[str, object] = {
        "inputs": assemble.package_inputs(
            stock, reference, bridge, runtime, seed, project_root=declared_project
        ),
        "final_root_sha256": digest_file(archive),
    }
    (output / "package-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    argv = ["--builder", "unused-cache-builder", "--output", str(output)]
    for name, path in zip(
        ("stock-root", "reference", "bridge", "runtime", "seed"),
        (stock, reference, bridge, runtime, seed),
        strict=True,
    ):
        argv.extend(["--" + name, str(path)])
    assert (
        assemble.package_command(
            argv, project_root=declared_project, docker=["unused-docker"]
        )
        == manifest
    )
    archive.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="fresh --output"):
        assemble.package_command(
            argv, project_root=declared_project, docker=["unused-docker"]
        )
    archive.write_bytes(b"complete exact layer")
    (declared_project / "build-assets/runtime/alsa.conf").write_text(
        "changed\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="fresh --output"):
        assemble.package_command(
            argv, project_root=declared_project, docker=["unused-docker"]
        )


def test_installed_builder_command_runs_outside_checkout(tmp_path: Path) -> None:
    """Installed command discovery requires neither source ancestry nor SSH."""
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "batocera_gow.builder.assemble", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--project-root" in completed.stdout
    assert "--image" in completed.stdout
