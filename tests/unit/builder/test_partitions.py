"""Validate GPT geometry and whole-root collision policy without I/O."""

import pytest

from batocera_gow.builder import assemble


@pytest.fixture
def partition_table() -> dict[str, object]:
    """Return a valid non-default-offset GPT with two filesystems."""
    return {
        "label": "gpt",
        "unit": "sectors",
        "sectorsize": 512,
        "firstlba": 34,
        "lastlba": 99966,
        "partitions": [
            {"start": 4096, "size": 40000, "type": assemble.EFI_TYPE},
            {"start": 45000, "size": 50000, "type": assemble.LINUX_TYPE},
        ],
    }


def test_offsets_use_reported_sector_size_and_start(
    partition_table: dict[str, object],
) -> None:
    """Byte offsets follow disk geometry rather than an assumed sector 2048."""
    parts = assemble.validate_partitions(
        {"partitiontable": partition_table}, 100000 * 512
    )
    assert parts[0]["offset"] == 4096 * 512
    partition_table["sectorsize"] = 4096
    assert (
        assemble.validate_partitions(
            {"partitiontable": partition_table}, 100000 * 4096
        )[1]["offset"]
        == 45000 * 4096
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start", -1),
        ("size", 0),
        ("size", True),
        ("size", 999999999999999999999),
        ("start", 1),
    ],
)
def test_invalid_arithmetic_and_bounds(
    partition_table: dict[str, object], field: str, value: int
) -> None:
    """Invalid extents cannot reach extraction or allocation."""
    partition_table["partitions"] = [
        dict(
            {"start": 4096, "size": 40000, "type": assemble.EFI_TYPE}, **{field: value}
        ),
        {"start": 45000, "size": 50000, "type": assemble.LINUX_TYPE},
    ]
    with pytest.raises(ValueError, match=r"positive integer|partition exceeds"):
        assemble.validate_partitions({"partitiontable": partition_table}, 100000 * 512)


@pytest.mark.parametrize(
    "change",
    [
        {"label": "dos"},
        {"sectorsize": 513},
        {"partitions": []},
        {
            "partitions": [
                {"start": 4096, "size": 40000, "type": assemble.LINUX_TYPE},
                {"start": 45000, "size": 50000, "type": assemble.LINUX_TYPE},
            ]
        },
        {
            "partitions": [
                {"start": 4096, "size": 40000, "type": assemble.EFI_TYPE},
                {"start": 40000, "size": 50000, "type": assemble.LINUX_TYPE},
            ]
        },
    ],
)
def test_overlapping_and_wrong_layout(
    partition_table: dict[str, object], change: dict[str, object]
) -> None:
    """Reject non-GPT, wrong geometry, wrong types and overlapping extents."""
    partition_table.update(change)
    with pytest.raises(ValueError, match=r"GPT|sector size|partitions|overlapping"):
        assemble.validate_partitions({"partitiontable": partition_table}, 100000 * 512)


def test_root_conflicts_only_allow_two_real_directories() -> None:
    """Shared directory metadata is legal; all other root collisions fail."""
    assert (
        assemble.path_conflicts({"usr": True, "usr/lib/core": False}, {"usr": True})
        == []
    )
    assert assemble.path_conflicts(
        {"usr": True, "link": False}, {"usr": False, "link": False}
    ) == ["link", "usr"]
