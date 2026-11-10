"""Validate remote shared-root observations against real temporary filesystems."""

import os
from pathlib import Path

import pytest

from batocera_gow.host.native_remote import (
    NativeError,
    OwnedState,
    identity,
    validate_shared_root,
)


def mount(root: Path, destination: str = "/wolf-local") -> list[dict[str, object]]:
    """Describe an observed writable bind.

    Args:
        root: Local backing directory represented in the container observation.
        destination: Container-visible mount destination.

    Returns:
        One complete Docker mount observation.
    """
    return [
        {"Source": str(root), "Destination": destination, "Type": "bind", "RW": True}
    ]


def test_shared_root_backing_mismatch_does_not_allocate(tmp_path: Path) -> None:
    """Matching path strings cannot replace equal backing identities."""
    root = tmp_path / "wolf"
    root.mkdir()
    pin = identity(root.stat())
    assert validate_shared_root(root, "/wolf-local", mount(root), pin[:2], []) == pin
    with pytest.raises(NativeError):
        validate_shared_root(root, "/wolf-local", mount(root), [pin[0], pin[1] + 1], [])
    with pytest.raises(NativeError):
        validate_shared_root(root, "/wolf-local", [], pin[:2], [])
    assert list(root.iterdir()) == []


def test_external_content_symlink_is_allowed_but_canonical_overlap_is_not(
    tmp_path: Path,
) -> None:
    """Authorized library aliases are not owned state and are never removed."""
    root, library = tmp_path / "wolf", tmp_path / "library"
    root.mkdir()
    library.mkdir()
    (library / "precious").write_text("keep", encoding="utf-8")
    alias = tmp_path / "content-alias"
    alias.symlink_to(library, target_is_directory=True)
    pin = identity(root.stat())
    validate_shared_root(root, "/wolf-local", mount(root), pin[:2], [str(alias)])
    alias.unlink()
    alias.symlink_to(root / "test-runs", target_is_directory=True)
    with pytest.raises(NativeError):
        validate_shared_root(root, "/wolf-local", mount(root), pin[:2], [str(alias)])
    assert (library / "precious").read_text(encoding="utf-8") == "keep"
    assert not (root / "test-runs").exists()


def test_symlinked_owned_parent_is_refused_before_writes(tmp_path: Path) -> None:
    """A test-runs alias cannot turn an arbitrary filesystem into shared state."""
    root, foreign = tmp_path / "wolf", tmp_path / "foreign"
    root.mkdir()
    foreign.mkdir()
    (root / "test-runs").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(NativeError):
        validate_shared_root(
            root, "/wolf-local", mount(root), identity(root.stat())[:2], []
        )
    assert list(foreign.iterdir()) == []


@pytest.mark.parametrize("leaf", [".native-control", ".native-evidence"])
def test_replaced_owned_child_is_retained(tmp_path: Path, leaf: str) -> None:
    """A stable home inode does not authorize deleting a replaced control tree."""
    state = OwnedState(tmp_path, "e" * 32, "owner", os.getuid(), os.getgid())
    pin = state.allocate()
    path = state.path / leaf
    path.rename(path.with_name(leaf + "-original"))
    path.mkdir()
    (path / "foreign").write_text("keep", encoding="utf-8")
    with pytest.raises(NativeError):
        state.remove(pin)
    assert (path / "foreign").read_text(encoding="utf-8") == "keep"
