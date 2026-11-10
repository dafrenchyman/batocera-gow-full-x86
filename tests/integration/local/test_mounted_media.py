"""Nonbootable metadata fixtures exercise selection and format, never guest boot."""

import json
import os
import struct
from pathlib import Path
from typing import TextIO

import pytest

from batocera_gow.runtime import mounted_media
from batocera_gow.runtime.media_catalog import load_catalog
from batocera_gow.runtime.mounted_media import (
    MediaError,
    inspect_media,
    read_selection,
    select_media,
    write_selection,
)


def library(tmp_path: Path, system: str = "nes") -> Path:
    """Create a synthetic content root with one stock-system directory.

    Args:
        tmp_path: Owned temporary parent.
        system: Stock ROM directory to create.

    Returns:
        The created library root.
    """
    root = tmp_path / "library"
    (root / system).mkdir(parents=True)
    return root


@pytest.mark.parametrize("state", ["missing", "empty", "unsupported"])
def test_absence_is_visible_untested_skip(tmp_path: Path, state: str) -> None:
    """Missing, empty and unsupported folders remain visible untested skips."""
    root = library(tmp_path)
    if state == "missing":
        (root / "nes").rmdir()
    if state == "unsupported":
        (root / "nes/readme.txt").write_bytes(b"synthetic notes")
    result = inspect_media(load_catalog().system("nes"), root)
    assert result.disposition == "Skipped: no compatible mounted media"
    assert not result.candidates


def test_remaining_libretro_routes_keep_formats_and_absence_case_local(
    tmp_path: Path,
) -> None:
    """Real stock selection cannot borrow a neighboring system's cartridge."""
    root = tmp_path / "library"
    entries = {
        "snes": "snes/selected.sfc",
        "megadrive": "megadrive/selected.md",
        "atari2600": "atari2600/selected.a26",
    }
    for relative in entries.values():
        path = root / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(b"Synthetic non-ROM bytes")
    # Each foreign extension is valid for a different required case.
    for relative in (
        "snes/foreign.a26",
        "megadrive/foreign.sfc",
        "atari2600/foreign.md",
    ):
        (root / relative).write_bytes(b"Wrong system's synthetic cartridge")
    catalog = load_catalog()
    for system, entry in entries.items():
        inspected = inspect_media(catalog.system(system), root)
        assert [candidate.relative_path for candidate in inspected.candidates] == [
            entry
        ]
        selected = select_media(inspected, lambda _count: 0)
        assert selected.system == system
        assert selected.entry == entry
    (root / "snes/selected.sfc").unlink()
    missing = inspect_media(catalog.system("snes"), root)
    assert missing.disposition == "Skipped: no compatible mounted media"
    assert not missing.candidates
    for system in ("megadrive", "atari2600"):
        selected = select_media(
            inspect_media(catalog.system(system), root), lambda _count: 0
        )
        assert selected.entry == entries[system]


def test_xbox_stock_formats_do_not_accept_raw_xbe_or_another_system_disc(
    tmp_path: Path,
) -> None:
    """Suffix eligibility uses real files, not a synthetic XISO boot assertion."""
    root = library(tmp_path, "xbox")
    (root / "xbox/default.xbe").write_bytes(b"Synthetic unsupported executable")
    (root / "xbox/disc.xiso").write_bytes(b"Synthetic unsupported suffix")
    (root / "xbox360").mkdir()
    (root / "xbox360/foreign.iso").write_bytes(b"Synthetic foreign-system disc")
    system = load_catalog().system("xbox")
    absent = inspect_media(system, root)
    assert absent.disposition == "Skipped: no compatible mounted media"
    assert not absent.candidates
    for name in ("disc.iso", "packed.squashfs"):
        (root / "xbox" / name).write_bytes(b"Synthetic selection bytes, not bootable")
    eligible = inspect_media(system, root)
    assert {candidate.relative_path for candidate in eligible.candidates} == {
        "xbox/disc.iso",
        "xbox/packed.squashfs",
    }
    selected = select_media(eligible, lambda _count: 0)
    assert selected.system == "xbox"
    assert selected.entry == "xbox/disc.iso"
    assert [member.relative_path for member in selected.members] == ["xbox/disc.iso"]


def xiso_metadata(
    path: Path,
    *,
    root_sector: int = 34,
    root_size: int = 28,
    image_size: int = 73728,
    partition_offset: int = 0,
) -> Path:
    """Write only public XDVDFS metadata and an empty data-file directory entry.

    The layout follows antangelo/xdvdfs at
    6b05af7fba79d567ef8c9698c8702b8d782248b8:
    xdvdfs-core/src/layout/{volume,disk_node,disk_data,region}.rs.
    Sector 32 has matching 20-byte signatures at offsets 0 and 0x7ec,
    followed by little-endian root-sector and byte-length fields at 0x14.
    No executable, firmware, guest program or private-media bytes are present.
    A shifted fixture models extraction-tool input, not supported xemu media.

    Args:
        path: Owned temporary image destination.
        root_sector: Root-directory sector relative to the partition start.
        root_size: Declared root-directory length in bytes.
        image_size: Sparse partition length in bytes.
        partition_offset: Leading sparse padding for unsupported shifted images.

    Returns:
        The created metadata-only image path.
    """
    volume = bytearray(b"\xa5" * 2048)
    volume[:20] = b"MICROSOFT*XBOX*MEDIA"
    volume[0x7EC:] = b"MICROSOFT*XBOX*MEDIA"
    struct.pack_into("<IIQ", volume, 0x14, root_sector, root_size, 123456789)
    with path.open("wb") as stream:
        stream.truncate(partition_offset + image_size)
        stream.seek(partition_offset + 65536)
        stream.write(volume)
        if root_size:
            stream.seek(partition_offset + root_sector * 2048)
            # One zero-length ordinary file. Its name is not exported evidence.
            stream.write(struct.pack("<HHIIBB", 0, 0, 0, 0, 0x20, 12) + b"metadata.txt")
    return path


@pytest.mark.parametrize(
    ("root_sector", "root_size", "image_size"),
    [
        (33, 28, 71680),
        (34, 28, 73728),
        (264, 2048, 544768),
        (47, 4097, 102400),
        (0, 0, 67584),
        (10, 0, 67584),
        (33, 0, 67584),
        (34, 28, 69660),
    ],
)
def test_xiso_structure_accepts_supported_root_offsets_without_mutation(
    tmp_path: Path, root_sector: int, root_size: int, image_size: int
) -> None:
    """Format evidence is descriptor/extent validation, not a bootability claim."""
    path = xiso_metadata(
        tmp_path / "private-disc.iso",
        root_sector=root_sector,
        root_size=root_size,
        image_size=image_size,
    )
    path.chmod(0o444)
    before = path.stat()
    original = path.read_bytes()
    evidence = mounted_media.inspect_xiso(path)
    assert evidence == {
        "format": "xdvdfs",
        "sector_size": 2048,
        "volume_offset": 65536,
        "image_size": image_size,
        "root_directory_sector": root_sector,
        "root_directory_size": root_size,
    }
    assert path.read_bytes() == original
    after = path.stat()
    assert (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mode,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    assert sorted(item.name for item in tmp_path.iterdir()) == ["private-disc.iso"]


@pytest.mark.parametrize(
    "damage",
    [
        "empty",
        "truncated-volume",
        "conventional-iso",
        "renamed-executable",
        "missing-leading-signature",
        "missing-trailing-signature",
        "root-start-outside-image",
        "root-end-outside-image",
        "maximum-root-sector",
        "maximum-root-size",
        "big-endian-root",
    ],
)
def test_xiso_structure_rejects_invalid_selected_media_without_mutation(
    tmp_path: Path, damage: str
) -> None:
    """A selected .iso stays an error, never a successful no-media disposition."""
    root = library(tmp_path, "xbox")
    path = xiso_metadata(root / "xbox/private-invalid.iso")
    with path.open("r+b") as stream:
        if damage == "empty":
            stream.truncate(0)
        elif damage == "truncated-volume":
            stream.truncate(67583)
        elif damage in ("conventional-iso", "renamed-executable"):
            stream.truncate(0)
            stream.truncate(73728)
            stream.seek(32768 if damage == "conventional-iso" else 0)
            stream.write(b"\x01CD001\x01" if damage == "conventional-iso" else b"XBEH")
        elif damage.startswith("missing-"):
            stream.seek(65536 if damage == "missing-leading-signature" else 67564)
            stream.write(b"not-an-xbox-signature")
        else:
            stream.seek(65556)
            if damage == "root-start-outside-image":
                stream.write(struct.pack("<II", 36, 28))
            elif damage == "root-end-outside-image":
                stream.write(struct.pack("<II", 35, 2049))
            elif damage == "maximum-root-sector":
                stream.write(struct.pack("<II", 0xFFFFFFFF, 28))
            elif damage == "maximum-root-size":
                stream.write(struct.pack("<II", 34, 0xFFFFFFFF))
            elif damage == "big-endian-root":
                stream.write(struct.pack(">II", 34, 28))
    path.chmod(0o444)
    before = path.stat()
    original = path.read_bytes()
    eligible = inspect_media(load_catalog().system("xbox"), root)
    assert eligible.disposition == "eligible"
    assert select_media(eligible, lambda _count: 0).entry == "xbox/private-invalid.iso"
    with pytest.raises(MediaError, match=r"(?i)xiso|xdvdfs") as caught:
        mounted_media.inspect_xiso(path)
    assert "private-invalid" not in str(caught.value)
    assert "Skipped: no compatible mounted media" not in str(caught.value)
    assert path.read_bytes() == original
    after = path.stat()
    assert (after.st_size, after.st_mode, after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_size,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    assert sorted(item.name for item in path.parent.iterdir()) == [
        "private-invalid.iso"
    ]


@pytest.mark.parametrize("partition_offset", [405798912, 265879552, 34078720])
def test_xiso_structure_does_not_reinterpret_shifted_full_disc_dumps(
    tmp_path: Path, partition_offset: int
) -> None:
    """Xdvdfs extraction offsets are not xemu raw-CD partition remapping.

    https://xemu.app/docs/disc-images/ explicitly excludes full redump images.
    Pinned xemu hw/ide/atapi.c reads LBA * 2048 without a partition offset.
    Keep these fixtures sparse and never read their large padding into memory.
    """
    path = xiso_metadata(
        tmp_path / "private-full-dump.iso", partition_offset=partition_offset
    )
    path.chmod(0o444)
    before = path.stat()
    with pytest.raises(MediaError, match=r"(?i)xiso|xdvdfs"):
        mounted_media.inspect_xiso(path)
    after = path.stat()
    assert (after.st_size, after.st_mode, after.st_mtime_ns, after.st_ctime_ns) == (
        before.st_size,
        before.st_mode,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    with path.open("rb") as stream:
        stream.seek(partition_offset + 65536)
        assert stream.read(20) == b"MICROSOFT*XBOX*MEDIA"


@pytest.mark.parametrize(
    "state", ["missing", "directory", "fifo", "symlink", "unreadable"]
)
def test_xiso_structure_unreadable_or_nonregular_image_has_private_safe_error(
    tmp_path: Path, state: str
) -> None:
    """Inspection refuses nonregular inputs without blocking or exposing paths."""
    path = tmp_path / "private-inaccessible.iso"
    target = xiso_metadata(tmp_path / "private-original.iso")
    original = target.read_bytes()
    if state == "directory":
        path.mkdir()
    elif state == "fifo":
        os.mkfifo(path)
    elif state == "symlink":
        path.symlink_to(target)
    elif state == "unreadable":
        path = target
        path.chmod(0o000)
    try:
        with pytest.raises(MediaError, match="XISO") as caught:
            mounted_media.inspect_xiso(path)
        assert "private-" not in str(caught.value)
        assert str(tmp_path) not in str(caught.value)
    finally:
        target.chmod(0o600)
    assert target.read_bytes() == original


def test_directory_access_and_symlink_errors_are_not_media_absence(
    tmp_path: Path,
) -> None:
    """Access and symlink failures are errors rather than missing-media skips."""
    root = library(tmp_path)
    (root / "nes").chmod(0o000)
    try:
        with pytest.raises(MediaError, match="discovery"):
            inspect_media(load_catalog().system("nes"), root)
    finally:
        (root / "nes").chmod(0o700)
    outside = tmp_path / "outside.nes"
    outside.write_bytes(b"synthetic secret")
    (root / "nes/link.nes").symlink_to(outside)
    with pytest.raises(MediaError, match="symlink"):
        inspect_media(load_catalog().system("nes"), root)
    with pytest.raises(MediaError):
        inspect_media(load_catalog().system("nes"), tmp_path / "missing-root")


def test_cue_companions_are_complete_and_tracks_are_not_independent(
    tmp_path: Path,
) -> None:
    """A CUE selection owns all tracks and detects changed companion bytes."""
    root = library(tmp_path, "psx")
    cue = root / "psx/disc.cue"
    cue.write_text('FILE "track.bin" BINARY\n  TRACK 01 MODE2/2352\n', encoding="utf-8")
    system = load_catalog().system("psx")
    incomplete = inspect_media(system, root)
    assert not incomplete.candidates
    assert incomplete.rejected == 1
    (root / "psx/track.bin").write_bytes(b"synthetic track")
    result = inspect_media(system, root)
    assert len(result.candidates) == 1
    selection = select_media(result, lambda _count: 0)
    assert selection.entry == "psx/disc.cue"
    assert {member.relative_path for member in selection.members} == {
        "psx/disc.cue",
        "psx/track.bin",
    }
    (root / "psx/track.bin").write_bytes(b"changed synthetic track")
    assert (
        select_media(inspect_media(system, root), lambda _count: 0).digest
        != selection.digest
    )


@pytest.mark.parametrize(
    "reference", ["../outside.bin", "/outside.bin", "nested/../../outside.bin"]
)
def test_descriptor_cannot_escape_selected_system(
    tmp_path: Path, reference: str
) -> None:
    """Descriptor traversal cannot reach outside its selected stock system."""
    root = library(tmp_path, "psx")
    (root / "psx/disc.cue").write_text(f'FILE "{reference}" BINARY\n', encoding="utf-8")
    with pytest.raises(MediaError, match="containment"):
        inspect_media(load_catalog().system("psx"), root)


def test_playlist_nested_companions_and_cycles(tmp_path: Path) -> None:
    """Nested playlists include all companions and reject recursive cycles."""
    root = library(tmp_path, "psx")
    (root / "psx/list.m3u").write_text("disc.cue\n", encoding="utf-8")
    (root / "psx/disc.cue").write_text('FILE "track.bin" BINARY\n', encoding="utf-8")
    (root / "psx/track.bin").write_bytes(b"synthetic")
    result = inspect_media(load_catalog().system("psx"), root)
    assert [candidate.relative_path for candidate in result.candidates] == [
        "psx/list.m3u"
    ]
    selected = select_media(result, lambda _count: 0)
    assert selected.entry == "psx/list.m3u"
    assert {member.relative_path for member in selected.members} == {
        "psx/list.m3u",
        "psx/disc.cue",
        "psx/track.bin",
    }
    (root / "psx/list.m3u").write_text("list.m3u\n", encoding="utf-8")
    assert inspect_media(load_catalog().system("psx"), root).rejected == 1


def test_selected_identity_is_private_reproducible_and_never_rerolled(
    tmp_path: Path,
) -> None:
    """Selection is private, reproducible and never rerolled after a change."""
    root = library(tmp_path)
    (root / "nes/a.nes").write_bytes(b"synthetic A")
    (root / "nes/b.NES").write_bytes(b"synthetic B")
    choices: list[int] = []

    def choose(count: int) -> int:
        """Choose the second entry and record the available population.

        Args:
            count: Number of eligible entries offered by the selector.

        Returns:
            The independently selected second-entry index.
        """
        choices.append(count)
        return 1

    eligible = inspect_media(load_catalog().system("nes"), root)
    selected = select_media(eligible, choose)
    assert choices == [2]
    assert selected.entry == "nes/b.NES"
    assert [(member.relative_path, member.size) for member in selected.members] == [
        ("nes/b.NES", len(b"synthetic B"))
    ]
    destination = tmp_path / "private"
    destination.mkdir(mode=0o700)
    record = destination / "selection.json"
    write_selection(record, selected)
    assert record.stat().st_mode & 0o777 == 0o600
    restored = read_selection(record, root)
    assert restored == selected
    assert json.loads(record.read_text(encoding="utf-8"))["entry"] == "nes/b.NES"
    with pytest.raises(MediaError, match="record"):
        write_selection(record, selected)
    (root / "nes/b.NES").write_bytes(b"changed")
    with pytest.raises(MediaError, match="changed"):
        read_selection(record, root)
    assert choices == [2]


def test_replaced_selected_file_fails_without_choosing_again(tmp_path: Path) -> None:
    """Replacing an eligible file by a link cannot trigger a fresh selection."""
    root = library(tmp_path)
    entry = root / "nes/a.nes"
    entry.write_bytes(b"synthetic")
    eligible = inspect_media(load_catalog().system("nes"), root)
    entry.unlink()
    entry.symlink_to(tmp_path / "foreign")
    with pytest.raises(MediaError):
        select_media(eligible, lambda _count: 0)


def test_unreadable_entry_and_non_rom_category_are_errors(tmp_path: Path) -> None:
    """Unreadable entries and non-ROM categories cannot claim media absence."""
    root = library(tmp_path)
    entry = root / "nes/a.nes"
    entry.write_bytes(b"synthetic")
    entry.chmod(0o000)
    with pytest.raises(MediaError):
        inspect_media(load_catalog().system("nes"), root)
    with pytest.raises(MediaError, match="ROM"):
        inspect_media(load_catalog().system("imageviewer"), root)


def test_paired_mdf_and_directory_media_require_their_contents(tmp_path: Path) -> None:
    """Paired discs and directory media are eligible only with their contents."""
    root = library(tmp_path, "psx")
    (root / "psx/disc.mdf").write_bytes(b"synthetic disc")
    assert not inspect_media(load_catalog().system("psx"), root).candidates
    (root / "psx/disc.mds").write_bytes(b"synthetic descriptor")
    selected = select_media(
        inspect_media(load_catalog().system("psx"), root), lambda _count: 0
    )
    assert selected.entry == "psx/disc.mdf"
    assert {member.relative_path for member in selected.members} == {
        "psx/disc.mdf",
        "psx/disc.mds",
    }
    (root / "ps3").mkdir()
    (root / "ps3/title.ps3").mkdir()
    assert not inspect_media(load_catalog().system("ps3"), root).candidates
    (root / "ps3/title.ps3/data").write_bytes(b"synthetic package data")
    selected = select_media(
        inspect_media(load_catalog().system("ps3"), root), lambda _count: 0
    )
    assert selected.entry == "ps3/title.ps3"
    assert [member.relative_path for member in selected.members] == [
        "ps3/title.ps3/data"
    ]


def test_clonecd_includes_optional_subchannels_without_requiring_them(
    tmp_path: Path,
) -> None:
    """CloneCD requires its image while including optional subchannel data."""
    root = library(tmp_path, "psx")
    (root / "psx/disc.ccd").write_bytes(b"synthetic descriptor")
    assert not inspect_media(load_catalog().system("psx"), root).candidates
    (root / "psx/disc.img").write_bytes(b"synthetic image")
    eligible = inspect_media(load_catalog().system("psx"), root)
    assert len(eligible.candidates) == 1
    selected = select_media(eligible, lambda _count: 0)
    assert selected.entry == "psx/disc.ccd"
    assert {member.relative_path for member in selected.members} == {
        "psx/disc.ccd",
        "psx/disc.img",
    }
    (root / "psx/disc.sub").write_bytes(b"synthetic subchannels")
    selected = select_media(
        inspect_media(load_catalog().system("psx"), root), lambda _count: 0
    )
    assert selected.entry == "psx/disc.ccd"
    assert {member.relative_path for member in selected.members} == {
        "psx/disc.ccd",
        "psx/disc.img",
        "psx/disc.sub",
    }


@pytest.mark.parametrize(
    ("system", "descriptor", "content", "companion"),
    [
        ("dreamcast", "disc.gdi", '1\n1 0 4 2352 "track.bin" 0\n', "track.bin"),
        ("psx", "disc.toc", 'CD_ROM\nDATAFILE "track.bin"\n', "track.bin"),
    ],
)
def test_other_disc_descriptors_require_referenced_tracks(
    tmp_path: Path, system: str, descriptor: str, content: str, companion: str
) -> None:
    """GDI and TOC selections retain the exact referenced track companions."""
    root = library(tmp_path, system)
    (root / system / descriptor).write_text(content, encoding="utf-8")
    assert not inspect_media(load_catalog().system(system), root).candidates
    (root / system / companion).write_bytes(b"synthetic track")
    selected = select_media(
        inspect_media(load_catalog().system(system), root), lambda _count: 0
    )
    assert selected.entry == f"{system}/{descriptor}"
    assert {member.relative_path for member in selected.members} == {
        f"{system}/{descriptor}",
        f"{system}/{companion}",
    }


def test_private_record_rejects_shared_parent_and_symlink(tmp_path: Path) -> None:
    """Private identity publication refuses shared parents and linked targets."""
    root = library(tmp_path)
    (root / "nes/test.nes").write_bytes(b"synthetic")
    selected = select_media(
        inspect_media(load_catalog().system("nes"), root), lambda _count: 0
    )
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(MediaError, match="owner-only"):
        write_selection(shared / "record.json", selected)
    shared.chmod(0o700)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"synthetic unrelated file")
    (shared / "record.json").symlink_to(foreign)
    with pytest.raises(MediaError):
        write_selection(shared / "record.json", selected)
    assert foreign.read_bytes() == b"synthetic unrelated file"


def test_all_six_absent_rows_remain_untested(tmp_path: Path) -> None:
    """Every required backend reports absent media without claiming coverage."""
    root = tmp_path / "empty-library"
    root.mkdir()
    results = [
        inspect_media(load_catalog().system(system), root)
        for system in ("nes", "snes", "megadrive", "atari2600", "psx", "xbox")
    ]
    assert all(
        result.disposition == "Skipped: no compatible mounted media"
        for result in results
    )
    assert not any(result.candidates for result in results)


def test_relative_track_reference_may_stay_inside_the_same_system(
    tmp_path: Path,
) -> None:
    """Relative companions may traverse directories within the selected system."""
    root = library(tmp_path, "psx")
    (root / "psx/discs").mkdir()
    (root / "psx/tracks").mkdir()
    (root / "psx/discs/disc.cue").write_text(
        'FILE "../tracks/track.bin" BINARY\n', encoding="utf-8"
    )
    (root / "psx/tracks/track.bin").write_bytes(b"synthetic track")
    selected = select_media(
        inspect_media(load_catalog().system("psx"), root), lambda _count: 0
    )
    assert {member.relative_path for member in selected.members} == {
        "psx/discs/disc.cue",
        "psx/tracks/track.bin",
    }


def test_reproduction_does_not_search_or_choose_unrelated_media(tmp_path: Path) -> None:
    """Reproduction reads only its identity, ignoring unrelated unsafe entries."""
    root = library(tmp_path)
    (root / "nes/chosen.nes").write_bytes(b"synthetic")
    selected = select_media(
        inspect_media(load_catalog().system("nes"), root), lambda _count: 0
    )
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    record = private / "record.json"
    write_selection(record, selected)
    (root / "nes/unrelated.nes").symlink_to(tmp_path / "foreign")
    assert read_selection(record, root) == selected


@pytest.mark.parametrize("interrupt", [False, True])
def test_private_record_publication_never_exposes_partial_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, interrupt: bool
) -> None:
    """A failed writer leaves no final record; readers see only complete identity."""
    root = library(tmp_path)
    (root / "nes/test.nes").write_bytes(b"synthetic non-ROM bytes")
    selected = select_media(
        inspect_media(load_catalog().system("nes"), root), lambda _size: 0
    )
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    destination = parent / "selection.json"
    original_dump = json.dump

    def partial_writer(value: object, stream: TextIO, *, sort_keys: bool) -> None:
        """Expose an interrupted write only through the unpublished temporary file.

        Args:
            value: Complete identity intended for publication.
            stream: Temporary output stream owned by the real writer.
            sort_keys: Preserve the production serializer's ordering request.

        Raises:
            OSError: If the scenario simulates an interrupted write.
        """
        stream.write('{"partial":')
        stream.flush()
        assert not destination.exists()
        if interrupt:
            message = "Synthetic interrupted record write"
            raise OSError(message)
        stream.seek(0)
        stream.truncate()
        original_dump(value, stream, sort_keys=sort_keys)

    monkeypatch.setattr(json, "dump", partial_writer)
    if interrupt:
        with pytest.raises(MediaError, match="creation failed"):
            write_selection(destination, selected)
        assert not list(parent.iterdir())
    else:
        write_selection(destination, selected)
        assert read_selection(destination, root) == selected
        assert list(parent.iterdir()) == [destination]
