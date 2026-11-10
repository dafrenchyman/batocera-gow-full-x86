"""Check stock metadata preservation and hostile archive refusal."""

import copy
import io
import json
import os
import stat
import tarfile
from pathlib import Path

import pytest

from batocera_gow.builder.inventory import (
    Inventory,
    Snapshot,
    saved_image_layer,
    validate_tar,
)


@pytest.fixture
def stock_root(tmp_path: Path) -> Path:
    """Create stock files, an absolute symlink and a real hardlink group."""
    (tmp_path / "usr/lib/libretro").mkdir(parents=True)
    (tmp_path / "usr/lib/libretro/core.so").write_bytes(b"complete upstream core")
    (tmp_path / "defaults").write_text("stock=true\n", encoding="utf-8")
    (tmp_path / "symlink").symlink_to("/usr/lib/libretro/core.so")
    os.link(tmp_path / "defaults", tmp_path / "hardlink")
    (tmp_path / "defaults").chmod(0o640)
    return tmp_path


def test_unmodified_tree_matches(stock_root: Path) -> None:
    """Complete inventory includes every path, not only selected libraries."""
    reference = Inventory(stock_root).capture()
    assert Inventory.compare(reference, Inventory(stock_root).capture())[
        "verified_stock_paths"
    ] == len(reference["entries"])


@pytest.mark.parametrize("change", ["remove-core", "defaults", "link"])
def test_removed_core_altered_defaults_and_link_fail(
    stock_root: Path, change: str
) -> None:
    """Stock content and symlink mutations are refused independently."""
    reference = Inventory(stock_root).capture()
    if change == "remove-core":
        (stock_root / "usr/lib/libretro/core.so").unlink()
    elif change == "defaults":
        (stock_root / "defaults").write_text("stock=false\n", encoding="utf-8")
    else:
        (stock_root / "symlink").unlink()
        (stock_root / "symlink").symlink_to("/wrong")
    with pytest.raises(ValueError, match=r"(removed|changed) stock path"):
        Inventory.compare(reference, Inventory(stock_root).capture())


def test_same_content_broken_hardlink_is_rejected(stock_root: Path) -> None:
    """Equal bytes cannot conceal a broken stock hardlink relationship."""
    reference = Inventory(stock_root).capture()
    (stock_root / "hardlink").unlink()
    (stock_root / "hardlink").write_text("stock=true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hardlinks"):
        Inventory.compare(reference, Inventory(stock_root).capture())


def test_only_isolated_additions_pass(stock_root: Path) -> None:
    """Nix and adapter additions pass; new files inside stock roots fail."""
    reference = Inventory(stock_root).capture()
    (stock_root / "nix/store/example").mkdir(parents=True)
    (stock_root / "nix/store/example/lib.so").write_bytes(b"isolated")
    (stock_root / "opt/gow-full-x86").mkdir(parents=True)
    (stock_root / "opt/gow-full-x86/entrypoint.sh").write_text(
        "true\n", encoding="utf-8"
    )
    for name, entry in reference["entries"].items():
        if entry["type"] == stat.S_IFDIR:
            assert "mtime_ns" in entry
            os.utime(
                stock_root / name.lstrip("/"), ns=(entry["mtime_ns"], entry["mtime_ns"])
            )
    assert (
        Inventory.compare(reference, Inventory(stock_root).capture())["added_paths"]
        == 7
    )
    (stock_root / "usr/new-library.so").write_bytes(b"not allowed")
    with pytest.raises(ValueError, match="unapproved addition"):
        Inventory.compare(reference, Inventory(stock_root).capture())


@pytest.mark.parametrize("field", ["mode", "uid", "gid", "mtime_ns", "xattrs"])
def test_mode_owner_timestamp_and_xattrs_are_compared(
    stock_root: Path, field: str
) -> None:
    """All stock metadata fields contribute to comparison, including ACLs."""
    reference = Inventory(stock_root).capture()
    changed: Snapshot = copy.deepcopy(reference)
    entry = changed["entries"]["/defaults"]
    if field == "mode":
        entry["mode"] = 0o777
    elif field == "uid":
        entry["uid"] = 9876
    elif field == "gid":
        entry["gid"] = 9877
    elif field == "mtime_ns":
        entry["mtime_ns"] = 42
    else:
        entry["xattrs"] = {"system.posix_acl_access": "encoded-acl"}
    with pytest.raises(ValueError, match=field):
        Inventory.compare(reference, changed)


def test_actual_xattr_is_captured(stock_root: Path) -> None:
    """A real binary xattr survives base64 capture and changes the inventory."""
    reference = Inventory(stock_root).capture()
    try:
        os.setxattr(stock_root / "defaults", "user.gow-fixture", b"metadata\x00value")
    except OSError as error:
        pytest.skip(f"filesystem has no user xattrs: {error}")
    assert (
        Inventory(stock_root).capture()["entries"]["/defaults"]["xattrs"][
            "user.gow-fixture"
        ]
        == "bWV0YWRhdGEAdmFsdWU="
    )
    with pytest.raises(ValueError, match="xattrs"):
        Inventory.compare(reference, Inventory(stock_root).capture())


def make_archive(path: Path, entries: list[tuple[str, bytes, str]]) -> None:
    """Write tar headers directly so hostile names are not normalized away."""
    with tarfile.open(path, "w") as archive:
        for name, kind, link in entries:
            entry = tarfile.TarInfo(name)
            entry.type, entry.linkname = kind, link
            archive.addfile(entry)


def test_absolute_stock_symlinks_do_not_allow_descendant_writes(tmp_path: Path) -> None:
    """Absolute symlinks are preserved but cannot become extraction parents."""
    path = tmp_path / "archive.tar"
    make_archive(path, [("lib", tarfile.SYMTYPE, "/usr/lib")])
    validate_tar(path)
    make_archive(
        path,
        [("lib", tarfile.SYMTYPE, "/usr/lib"), ("lib/injected", tarfile.REGTYPE, "")],
    )
    with pytest.raises(ValueError, match="traverses non-directory"):
        validate_tar(path)


@pytest.mark.parametrize(
    "entries",
    [
        [("../escape", tarfile.REGTYPE, "")],
        [("/etc/passwd", tarfile.REGTYPE, "")],
        [("link", tarfile.LNKTYPE, "../escape")],
        [("same", tarfile.REGTYPE, ""), ("same", tarfile.REGTYPE, "")],
    ],
)
def test_unsafe_archive_members_are_rejected(
    tmp_path: Path, entries: list[tuple[str, bytes, str]]
) -> None:
    """Refuse escaping members, unsafe links and duplicate writes."""
    path = tmp_path / "archive.tar"
    make_archive(path, entries)
    with pytest.raises(ValueError, match=r"(unsafe|duplicate) archive|unsafe hardlink"):
        validate_tar(path)


def test_saved_image_requires_single_filesystem_layer(tmp_path: Path) -> None:
    """Inventory cannot accidentally inspect just one layer of a layered image."""
    archive = tmp_path / "saved.tar"
    with tarfile.open(archive, "w") as saved:
        manifest = json.dumps([{"Layers": ["one.tar", "two.tar"]}]).encode()
        entry = tarfile.TarInfo("manifest.json")
        entry.size = len(manifest)
        saved.addfile(entry, io.BytesIO(manifest))
    with pytest.raises(ValueError, match="one flattened filesystem layer"):
        saved_image_layer(archive, tmp_path)


def test_saved_layer_bytes_are_not_repacked(tmp_path: Path) -> None:
    """The saved-image reader preserves the exact original layer stream."""
    layer_bytes = b"exact layer including arbitrary pax layout\x00"
    archive = tmp_path / "saved.tar"
    with tarfile.open(archive, "w") as saved:
        for name, content in [
            ("manifest.json", b'[{"Layers":["layer.tar"]}]'),
            ("layer.tar", layer_bytes),
        ]:
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            saved.addfile(entry, io.BytesIO(content))
    assert saved_image_layer(archive, tmp_path).read_bytes() == layer_bytes


def test_symlink_target_spelling_is_preserved(stock_root: Path) -> None:
    """Stock symlink targets retain repeated separators and dot components."""
    (stock_root / "raw-link").symlink_to("usr//lib/./libretro/core.so")
    entry = Inventory(stock_root).capture()["entries"]["/raw-link"]
    assert entry.get("target") == "usr//lib/./libretro/core.so"
