"""Exercise native state ownership on real temporary filesystems."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from batocera_gow.host.native_remote import (
    NativeError,
    OwnedState,
    identity,
    open_directory,
)
from batocera_gow.runtime.media_catalog import DEFAULT_CATALOG, load_catalog
from batocera_gow.runtime.mounted_media import (
    MediaError,
    inspect_media,
    select_media,
    write_selection,
)
from batocera_gow.runtime.native_checks import qualified_input
from batocera_gow.runtime.native_diagnostics import input_permitted, publish_json


def test_exclusive_allocation_and_removal_preserve_foreign_state(
    tmp_path: Path,
) -> None:
    """Only a matching run allocation can authorize recursive removal."""
    foreign = tmp_path / "profile-data" / "user" / "WolfExperimental"
    foreign.mkdir(parents=True)
    (foreign / "save").write_text("keep", encoding="utf-8")
    state = OwnedState(tmp_path, "a" * 32, "secret-owner", os.getuid(), os.getgid())
    pin = state.allocate()
    (state.path / "userdata").mkdir()
    (state.path / "userdata" / "save").write_text("test", encoding="utf-8")
    with pytest.raises((FileExistsError, NativeError)):
        state.allocate()
    state.remove(pin)
    assert not state.path.exists()
    assert (foreign / "save").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("run_id", ["../foreign", "/absolute", "", "a/b", "."])
def test_traversal_never_allocates(tmp_path: Path, run_id: str) -> None:
    """Names cannot escape the dedicated test-runs parent."""
    with pytest.raises(NativeError):
        OwnedState(tmp_path, run_id, "token", os.getuid(), os.getgid())
    assert list(tmp_path.iterdir()) == []


def test_replaced_home_is_retained(tmp_path: Path) -> None:
    """A valid ownership token does not override an inode replacement."""
    state = OwnedState(tmp_path, "b" * 32, "token", os.getuid(), os.getgid())
    pin = state.allocate()
    original = state.path.with_name("original")
    state.path.rename(original)
    state.path.mkdir()
    (state.path / "foreign").write_text("keep", encoding="utf-8")
    with pytest.raises(NativeError):
        state.remove(pin)
    assert (state.path / "foreign").exists()
    assert original.exists()


def test_symlinked_parent_and_replaced_marker_are_refused(tmp_path: Path) -> None:
    """Rejected links never authorize removing their foreign targets."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "test-runs").symlink_to(foreign, target_is_directory=True)
    state = OwnedState(root, "c" * 32, "token", os.getuid(), os.getgid())
    with pytest.raises((OSError, NativeError)):
        state.allocate()
    assert list(foreign.iterdir()) == []
    (root / "test-runs").unlink()
    pin = state.allocate()
    marker = state.path / ".native-owner"
    marker.unlink()
    marker.symlink_to(foreign / "precious")
    with pytest.raises((OSError, NativeError)):
        state.remove(pin)
    assert state.path.exists()


def test_directory_open_refuses_intermediate_symlink(tmp_path: Path) -> None:
    """Anchoring every component is stronger than checking the leaf only."""
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(NotADirectoryError):
        open_directory(tmp_path / "link" / "child")
    descriptor = open_directory(tmp_path / "real")
    try:
        assert identity(os.fstat(descriptor)) == identity((tmp_path / "real").stat())
    finally:
        os.close(descriptor)


def test_atomic_report_publication_preserves_existing_evidence(tmp_path: Path) -> None:
    """A completed JSON file appears only once and cannot replace any file."""
    path = tmp_path / "report.json"
    publish_json(path, {"status": "passed"})
    original = path.read_bytes()
    assert path.stat().st_mode & 0o077 == 0
    assert not path.with_name("report.json.partial").exists()
    with pytest.raises(FileExistsError):
        publish_json(path, {"status": "different"})
    assert path.read_bytes() == original
    assert not path.with_name("report.json.partial").exists()


def test_serialization_failure_cannot_publish_partial_report(tmp_path: Path) -> None:
    """Invalid observations never become a visible completion marker."""
    with pytest.raises(TypeError):
        publish_json(tmp_path / "report.json", {"invalid": object()})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True])
def test_invalid_native_lease_cannot_authorize_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, value: float | bool
) -> None:
    """Invalid lifetime data is a refusal even in an otherwise regular file."""
    lease = tmp_path / "lease"
    lease.write_text(json.dumps({"expires": value}), encoding="utf-8")
    lease.chmod(0o600)
    monkeypatch.setenv("GOW_NATIVE_LEASE", str(lease))
    with pytest.raises(InterruptedError):
        input_permitted()


def test_fifo_lease_refusal_is_bounded_in_a_real_process(tmp_path: Path) -> None:
    """A non-regular permission path cannot block before its type is checked."""
    lease = tmp_path / "lease"
    os.mkfifo(lease, 0o600)
    # Fixed interpreter and program, no shell; the temporary lease is environment data.
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "from batocera_gow.runtime.native_diagnostics "
                "import input_permitted; input_permitted()"
            ),
        ],
        env=dict(os.environ, GOW_NATIVE_LEASE=str(lease)),
        text=True,
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert process.returncode != 0
    assert "Native input permission unavailable" in process.stderr


@pytest.mark.parametrize(
    "damage",
    ["none", "catalog", "media", "selection", "system", "profile", "writable-firmware"],
)
# Keep the complete stock replay and each real filesystem mutation in one scenario.
def test_installed_qualified_replay_uses_pinned_stock_catalog(  # noqa: PLR0915
    tmp_path: Path, damage: str
) -> None:
    """Real packaged readers reject changed inputs without host-layout assets."""
    installed = tmp_path / "opt/gow-full-x86"
    installed.mkdir(parents=True)
    catalog = tmp_path / "usr/share/emulationstation/es_systems.cfg"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(DEFAULT_CATALOG.read_bytes())
    roms = tmp_path / "home/retro/userdata/roms"
    (roms / "nes").mkdir(parents=True)
    (tmp_path / "userdata").symlink_to(roms.parent, target_is_directory=True)
    media = roms / "nes/synthetic.nes"
    media.write_bytes(b"not executable console content")
    selection = select_media(
        inspect_media(load_catalog(catalog).system("nes"), roms),
        lambda _count: 0,
    )
    control = tmp_path / "home/retro/.native-control"
    control.mkdir(parents=True, mode=0o700)
    write_selection(control / "selection.json", selection)
    template = installed / "suite-es-input.cfg"
    template.write_text("synthetic mapping {guid}", encoding="utf-8")
    definition = installed / "suite-gamepad.json"
    definition.write_text("synthetic controller definition", encoding="utf-8")
    expected: dict[str, object] = {
        "backend": "libretro",
        "system": selection.system,
        "media": {"identity": selection.digest},
        "profile": {
            "guid": "a" * 32,
            "sha256": hashlib.sha256(
                ("synthetic mapping " + "a" * 32).encode(),
            ).hexdigest(),
            "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
            "definition_sha256": hashlib.sha256(definition.read_bytes()).hexdigest(),
        },
    }
    if damage == "catalog":
        with catalog.open("ab") as stream:
            stream.write(b"\n")
    elif damage == "media":
        media.write_bytes(b"changed synthetic content")
    elif damage == "selection":
        alternate = roms / "nes/alternate.nes"
        alternate.write_bytes(b"different synthetic non-ROM content")
        replacement = select_media(
            inspect_media(load_catalog(catalog).system("nes"), roms),
            lambda _count: 0,
        )
        (control / "selection.json").unlink()
        write_selection(control / "selection.json", replacement)
    elif damage == "system":
        expected["system"] = "snes"
    elif damage == "profile":
        template.write_text("changed mapping", encoding="utf-8")
    elif damage == "writable-firmware":
        expected["backend"] = "xemu"
        bios = tmp_path / "userdata/bios"
        bios.mkdir()
        (bios / "mcpx_1.0.bin").write_bytes(b"synthetic non-firmware")
        (bios / "Complex_4627.bin").write_bytes(b"synthetic non-firmware")
        hdd = tmp_path / "usr/share/xemu/data/xbox_hdd.qcow2"
        hdd.parent.mkdir(parents=True)
        hdd.write_bytes(b"synthetic non-firmware")
        expected["prerequisites"] = {
            "mcpx": {"identity": hashlib.sha256(b"synthetic non-firmware").hexdigest()},
            "bios": {"identity": hashlib.sha256(b"synthetic non-firmware").hexdigest()},
            "hdd": {
                "source_identity": hashlib.sha256(b"synthetic non-firmware").hexdigest()
            },
        }
    errors = {
        "catalog": MediaError,
        "media": MediaError,
        "writable-firmware": ValueError,
    }
    if damage in errors:
        with pytest.raises(errors[damage]):
            qualified_input(expected, root=tmp_path)
    else:
        assert qualified_input(expected, root=tmp_path) is (damage == "none")
    assert not (control / "lease").exists()


def test_qualified_reader_process_refuses_private_malformed_request(
    tmp_path: Path,
) -> None:
    """The installed process returns only a refusal for malformed private input."""
    # Fixed installed module argv; private input travels only over stdin.
    process = subprocess.run(
        [sys.executable, "-B", "-m", "batocera_gow.runtime.native_checks", "qualified"],
        input=json.dumps({"private": str(tmp_path / "private-title")}),
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert process.returncode == 0
    assert json.loads(process.stdout) == {"matched": False}
    assert process.stderr == ""


def test_partial_allocation_failure_removes_only_new_owned_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed ownership setup removes its partial allocation, never foreign data."""
    foreign = tmp_path / "test-runs" / "foreign"
    foreign.mkdir(parents=True)
    (foreign / "save").write_bytes(b"keep foreign state")
    state = OwnedState(tmp_path, "f" * 32, "owner", os.getuid(), os.getgid())

    def refuse_ownership(
        _path: str,
        _uid: int,
        _gid: int,
        *,
        dir_fd: int,
        follow_symlinks: bool,
    ) -> None:
        """Fail a real ownership boundary after partial state has been created.

        Args:
            _path: Child selected by the allocator for ownership setup.
            _uid: Intended application user.
            _gid: Intended application group.
            dir_fd: Open descriptor anchoring the newly allocated home.
            follow_symlinks: Whether the allocator would follow a child link.

        Raises:
            OSError: Always, to simulate failed filesystem ownership setup.
        """
        assert not follow_symlinks
        assert os.stat(".native-control", dir_fd=dir_fd).st_ino
        message = "Synthetic ownership setup failure"
        raise OSError(message)

    monkeypatch.setattr(os, "chown", refuse_ownership)
    with pytest.raises(OSError, match="Synthetic ownership setup failure"):
        state.allocate()
    assert not state.path.exists()
    assert (foreign / "save").read_bytes() == b"keep foreign state"
