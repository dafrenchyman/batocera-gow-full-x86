"""Exercise confined state transactions and ownership-safe runtime startup failures."""

import errno
import json
import os
import pwd
import runpy
import shutil
import socket
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Never

import pytest

from batocera_gow.runtime import runtime

STOCK_ACTION_NAME = "_Daemon__handle_actions"


class ApplianceFiles:
    """Keep appliance names and descriptor-relative writes in disposable storage."""

    def __init__(self, root: Path) -> None:
        """Select a directory owned by this test, never a production root."""
        self.root = root
        self.home = root / "home/retro"

    def __call__(self, value: str | Path) -> Path:
        """Redirect absolute appliance names without remapping owned paths."""
        path = Path(value)
        if path.is_absolute() and not path.is_relative_to(self.root):
            return self.root / path.relative_to("/")
        return path

    def file(self, name: str, contents: str) -> Path:
        """Create an ordinary file below the owned appliance root."""
        path = self(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path


class SyntheticOwnership:
    """Confine descriptor writes while modeling only the root prerequisite."""

    def __init__(self, paths: ApplianceFiles, monkeypatch: pytest.MonkeyPatch) -> None:
        """Capture real filesystem operations before injecting ownership."""
        self.paths = paths
        self.original_open = os.open
        self.original_fstat = os.fstat
        self.original_fchown = os.fchown
        self.original_chown = os.chown
        self.original_stat = os.stat
        self.transferred: set[Path] = set()
        monkeypatch.setattr(os, "open", self.open_owned)
        monkeypatch.setattr(os, "fstat", self.synthetic_root_stat)
        monkeypatch.setattr(os, "fchown", self.transfer_descriptor)
        monkeypatch.setattr(os, "chown", self.transfer_path)
        monkeypatch.setattr(os, "stat", self.stat_owned)

    @staticmethod
    def descriptor_path(descriptor: int) -> Path:
        """Read the kernel's target for an actual open descriptor."""
        return Path(f"/proc/self/fd/{descriptor}").readlink()

    def open_owned(
        self,
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        """Rebase root-relative traversal and reject writes outside the fixture."""
        selected = Path(path)
        if str(path) == "/":
            selected = self.paths.root
        elif dir_fd is not None:
            parent = self.descriptor_path(dir_fd)
            # StateInitializer walks the real absolute home through its pinned
            # root FD. Rejoin that owned subtree without requiring a chroot.
            if parent == self.paths.root and str(path) == self.paths.home.parts[1]:
                selected = Path("/") / self.paths.home.parts[1]
            else:
                selected = parent / selected
        if flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            assert selected.is_relative_to(self.paths.root)
        return self.original_open(selected, flags, mode)

    def synthetic_root_stat(self, descriptor: int) -> os.stat_result:
        """Model trusted root ancestors and untransferred generated files."""
        info = self.original_fstat(descriptor)
        path = self.descriptor_path(descriptor)
        generated = self.paths.home / "userdata/system/.gow-full-x86-generated"
        root_directory = (
            path == self.paths.root
            or (self.paths.home.is_relative_to(path) and path != self.paths.home)
            or path.is_relative_to(self.paths("/usr"))
        )
        new_generated = path.is_relative_to(generated) and path not in self.transferred
        if root_directory or new_generated:
            values = list(info)
            values[4] = 0
            values[5] = os.getegid() if new_generated else 0
            if root_directory:
                values[0] = info.st_mode & ~0o022
            return os.stat_result(values)
        return info

    def transfer_descriptor(self, descriptor: int, uid: int, gid: int) -> None:
        """Perform real ownership transfer only within disposable storage."""
        path = self.descriptor_path(descriptor)
        assert path.is_relative_to(self.paths.root)
        assert (uid, gid) == (os.getuid(), os.getgid())
        self.original_fchown(descriptor, uid, gid)
        self.transferred.add(path)

    def transfer_path(
        self,
        path: str | os.PathLike[str],
        uid: int,
        gid: int,
        *,
        follow_symlinks: bool = True,
    ) -> None:
        """Reject ownership changes to anything outside the fixture."""
        assert Path(path).is_relative_to(self.paths.root)
        assert (uid, gid) == (os.getuid(), os.getgid())
        self.original_chown(path, uid, gid, follow_symlinks=follow_symlinks)

    def stat_owned(
        self,
        path: str | os.PathLike[str] | int,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        """Model the two root-owned paths inspected without descriptors."""
        selected_path = path
        selected_fd = dir_fd
        if not isinstance(path, int) and dir_fd is not None:
            parent = self.descriptor_path(dir_fd)
            if parent == self.paths.root and str(path) == self.paths.home.parts[1]:
                # Match open_owned's read-only escape into the real ancestor
                # walk, so final no-follow inode rechecks inspect the same path.
                selected_path = Path("/") / self.paths.home.parts[1]
                selected_fd = None
        info = self.original_stat(
            selected_path, dir_fd=selected_fd, follow_symlinks=follow_symlinks
        )
        if isinstance(path, int):
            return info
        selected = Path(path)
        if dir_fd is not None:
            selected = self.descriptor_path(dir_fd) / selected
        if selected in (
            self.paths("/usr/share/duckstation/resources/gamecontrollerdb.txt"),
            self.paths.root / "tmp/.X11-unix",
        ):
            values = list(info)
            values[4:6] = [0, 0]
            return os.stat_result(values)
        return info


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApplianceFiles:
    """Inject confined paths and synthetic root ownership, not native privileges."""
    paths = ApplianceFiles(tmp_path)
    monkeypatch.setattr(runtime, "Path", paths)
    SyntheticOwnership(paths, monkeypatch)
    return paths


class PopulationBoundary:
    """Model only external extraction and stock-script filesystem effects."""

    def __init__(self, files: ApplianceFiles, damage: str = "") -> None:
        """Select an explicit external failure or corrupt population output."""
        self.files = files
        self.damage = damage
        self.extractions = 0
        self.populations = 0
        self.archive = files.root / "archive"
        self.archive.mkdir()
        (self.archive / "roms/preexisting").mkdir(parents=True)
        (self.archive / "roms/preexisting/keep.txt").write_bytes(b"archive defaults")
        (self.archive / "bios").mkdir()
        (self.archive / "saves").mkdir()
        (self.archive / "saves/default.cfg").write_bytes(b"seed save configuration")
        files.file("/usr/share/batocera/batocera.version", "43.1\n")
        files.file(
            "/usr/share/batocera/datainit/roms/new-system/subdir/demo.rom",
            "legal fixture\n",
        )
        files.file(
            "/usr/share/batocera/datainit/roms/preexisting/unused.rom", "not reseeded\n"
        )
        source = files("/usr/share/batocera/datainit/roms/new-system")
        (source / "alias.rom").symlink_to("subdir/demo.rom")
        files("/usr/share/batocera/datainit/roms/linked-system").symlink_to(
            "new-system"
        )
        files.file("/usr/share/duckstation/resources/stock.txt", "untouched\n")
        files.file("/etc/machine-id", "old disposable identity\n")
        files.file("/var/lib/dbus/machine-id", "old disposable identity\n")
        files.file("/boot/placeholder", "disposable\n")
        files.file(
            "/assets/es_systems_gow_duckstation.cfg",
            "<systemList><system><name>psx</name>"
            "<command>fixture launcher</command></system></systemList>\n",
        )
        for name in ("roms", "bios"):
            (files.home / "userdata" / name).mkdir(parents=True)

    def __call__(
        self,
        command: Sequence[str],
        *,
        check: bool,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """Supply external effects, never replace the state transition rules."""
        del env, timeout
        assert check
        if Path(command[0]).name == "tar":
            self.extractions += 1
            stage = Path(command[-1])
            shutil.copytree(self.archive, stage, dirs_exist_ok=True, symlinks=True)
            if self.damage == "extract":
                raise subprocess.CalledProcessError(2, command)
        elif command[1:] == ["/etc/init.d/S12populateshare", "start"]:
            self.populations += 1
            stage = self.files("/userdata").resolve(strict=True)
            system = stage / "system"
            (system / "data.version").write_text("43.1\n", encoding="utf-8")
            (system / "machine-id").write_text(
                "stable-fixture-identity\n", encoding="utf-8"
            )
            (system / "batocera.conf").write_text(
                "system.language=en_US\n", encoding="utf-8"
            )
            source = self.files("/usr/share/batocera/datainit/roms/new-system")
            shutil.copytree(source, stage / "roms/new-system", symlinks=True)
            if self.damage == "population":
                raise subprocess.CalledProcessError(7, command)
            if self.damage == "seed-bytes":
                (stage / "roms/new-system/subdir/demo.rom").write_bytes(b"damaged")
            elif self.damage == "seed-link":
                (stage / "roms/new-system/alias.rom").unlink()
                (stage / "roms/new-system/alias.rom").symlink_to("wrong.rom")
            elif self.damage == "identity":
                (system / "machine-id").write_bytes(b"")
            elif self.damage == "collision":
                (self.files.home / "userdata/saves").mkdir()
                (self.files.home / "userdata/saves/foreign").write_bytes(
                    b"concurrent content"
                )
        else:
            pytest.fail(f"Unexpected external command: {command!r}")
        return subprocess.CompletedProcess(command, 0, b"", b"")


@pytest.fixture
def population(
    files: ApplianceFiles, monkeypatch: pytest.MonkeyPatch
) -> PopulationBoundary:
    """Supply deterministic stock inputs while keeping all filesystem rules real."""
    boundary = PopulationBoundary(files)
    monkeypatch.setattr(runtime, "HERE", files("/assets"))
    monkeypatch.setattr(subprocess, "run", boundary)
    # Resolution only: these paths are consumed by the external command boundary.
    monkeypatch.setattr(shutil, "which", lambda name: "/fixture/bin/" + name)
    return boundary


def test_new_state_is_published_last_and_reentry_preserves_user_changes(
    files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Seed once, retain library identities and never repopulate marked userdata."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    libraries = {name: (state.final / name).stat().st_ino for name in ("roms", "bios")}
    state.run()
    assert json.loads(state.marker.read_text(encoding="utf-8")) == {
        "release": "43.1",
        "puid": os.getuid(),
        "pgid": os.getgid(),
    }
    assert not state.work.exists()
    assert not (files.home / ".gow-full-x86-state.json.partial").exists()
    assert (
        state.final / "saves/default.cfg"
    ).read_bytes() == b"seed save configuration"
    assert (
        state.seed / "roms/new-system/subdir/demo.rom"
    ).read_bytes() == b"legal fixture\n"
    assert (state.seed / "roms/new-system/alias.rom").readlink() == Path(
        "subdir/demo.rom"
    )
    assert not (state.seed / "roms/preexisting/unused.rom").exists()
    assert {name: (state.final / name).stat().st_ino for name in libraries} == libraries
    assert all(not any((state.final / name).iterdir()) for name in libraries)
    assert files("/userdata").readlink() == state.final
    for name in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        assert files(name).readlink() == Path("/userdata/system/machine-id")
    database = (
        state.final / "system/.gow-full-x86-generated/duckstation/gamecontrollerdb.txt"
    )
    assert database.read_bytes() == b""
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert (
        files("/usr/share/duckstation/resources/gamecontrollerdb.txt").readlink()
        == database
    )
    override = (
        state.final / "system/configs/emulationstation/es_systems_gow_duckstation.cfg"
    )
    assert (
        override.read_bytes()
        == files("/assets/es_systems_gow_duckstation.cfg").read_bytes()
    )
    identity = state.final / "system/machine-id"
    identity_inode = identity.stat().st_ino
    marker_inode = state.marker.stat().st_ino
    database.write_bytes(b"operator controller mapping\n")
    override.write_bytes(b"operator-owned catalog\n")
    (state.final / "system/batocera.conf").write_text(
        "system.language=fr_FR\n", encoding="utf-8"
    )
    state.run()
    assert (population.extractions, population.populations) == (1, 1)
    assert identity.stat().st_ino == identity_inode
    assert state.marker.stat().st_ino == marker_inode
    assert identity.read_text(encoding="utf-8") == "stable-fixture-identity\n"
    assert database.read_bytes() == b"operator controller mapping\n"
    assert override.read_bytes() == b"operator-owned catalog\n"
    assert (state.final / "system/batocera.conf").read_text(
        encoding="utf-8"
    ) == "system.language=fr_FR\n"
    assert (files("/usr/share/duckstation/resources/stock.txt")).read_text(
        encoding="utf-8"
    ) == "untouched\n"


@pytest.mark.parametrize("missing", [("roms",), ("bios",), ("roms", "bios")])
def test_home_libraries_are_seeded_only_when_absent(
    missing: tuple[str, ...], files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Initialize without library mounts and preserve operator content on reentry."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    retained = {}
    for name in ("roms", "bios"):
        library = state.final / name
        if name in missing:
            library.rmdir()
        else:
            content = library / "operator-file"
            content.write_bytes(b"operator library content")
            retained[name] = content.stat().st_ino
    state.run()
    if "roms" in missing:
        assert (
            state.final / "roms/new-system/subdir/demo.rom"
        ).read_bytes() == b"legal fixture\n"
        assert (state.final / "roms/new-system/alias.rom").readlink() == Path(
            "subdir/demo.rom"
        )
    for name in ("roms", "bios"):
        content = state.final / name / "operator-file"
        if name in retained:
            assert content.stat().st_ino == retained[name]
            assert content.read_bytes() == b"operator library content"
        else:
            content.write_bytes(b"added after initialization")
    state.run()
    for name in ("roms", "bios"):
        expected = (
            b"operator library content"
            if name in retained
            else b"added after initialization"
        )
        assert (state.final / name / "operator-file").read_bytes() == expected
    assert (population.extractions, population.populations) == (1, 1)


@pytest.mark.parametrize(
    "damage",
    ["extract", "population", "seed-bytes", "seed-link", "identity", "collision"],
)
def test_failed_initialization_never_publishes_success_or_retries_partial_state(
    damage: str, files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Retain interrupted evidence and refuse a second population over it."""
    population.damage = damage
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        state.run()
    assert not state.marker.exists()
    assert state.work.exists() or state.seed.exists()
    assert not (files.home / ".gow-full-x86-state.json.partial").exists()
    if damage == "collision":
        assert (state.final / "saves/foreign").read_bytes() == b"concurrent content"
    elif damage in {"seed-bytes", "seed-link", "population"}:
        assert (state.stage / "system/machine-id").read_text(
            encoding="utf-8"
        ) == "stable-fixture-identity\n"
        assert not (state.final / "system").exists()
    counts = population.extractions, population.populations
    with pytest.raises(RuntimeError, match="interrupted or unrelated initialization"):
        state.run()
    assert (population.extractions, population.populations) == counts


@pytest.mark.parametrize("damage", ["escape", "version-link", "postshare"])
def test_unsafe_seed_or_boot_hook_is_refused_before_population(
    damage: str, files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Do not execute stock initialization on redirected identity or user hooks."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    if damage == "postshare":
        files.file("/boot/postshare.sh", "operator content\n")
        reason = "unexpected /boot/postshare.sh"
    else:
        system = population.archive / "system"
        system.mkdir()
        if damage == "escape":
            (system / "foreign").symlink_to(files.root / "outside")
            reason = "SHARE seed symlink escapes"
        else:
            (system / "version-source").write_text("43.1\n", encoding="utf-8")
            (system / "data.version").symlink_to("version-source")
            reason = "seed data.version is a symlink"
    with pytest.raises(RuntimeError, match=reason):
        state.run()
    assert population.populations == 0
    assert not state.marker.exists()
    if damage == "postshare":
        assert (
            files("/boot/postshare.sh").read_text(encoding="utf-8")
            == "operator content\n"
        )
        assert population.extractions == 0


@pytest.mark.parametrize("existing", ["missing", "empty", "recognized"])
def test_safe_link_replaces_only_recognized_empty_destinations(
    existing: str, tmp_path: Path
) -> None:
    """Allow an absent name, empty directory or explicit previous link target."""
    link = tmp_path / "userdata"
    target = tmp_path / "final"
    previous = tmp_path / "stage"
    if existing == "empty":
        link.mkdir()
    elif existing == "recognized":
        link.symlink_to(previous)
    runtime.safe_link(link, target, allowed=(previous,))
    assert link.is_symlink()
    assert link.readlink() == target


@pytest.mark.parametrize(
    "existing", ["file", "nonempty", "foreign-link", "normalized-link"]
)
def test_safe_link_preserves_conflicts_including_different_target_spelling(
    existing: str, tmp_path: Path
) -> None:
    """Never erase content or accept a lexically different link as recognized."""
    link = tmp_path / "userdata"
    target = tmp_path / "final"
    if existing == "file":
        link.write_bytes(b"operator file")
    elif existing == "nonempty":
        link.mkdir()
        (link / "keep").write_bytes(b"operator directory")
    else:
        link.symlink_to(
            str(target) + "/" if existing == "normalized-link" else "foreign"
        )
    inode = link.lstat().st_ino
    with pytest.raises(RuntimeError, match=r"conflicting path|unrecognized symlink"):
        runtime.safe_link(link, target)
    assert link.lstat().st_ino == inode
    if existing == "file":
        assert link.read_bytes() == b"operator file"
    elif existing == "nonempty":
        assert (link / "keep").read_bytes() == b"operator directory"
    else:
        # Path.readlink drops the trailing slash that this contract distinguishes.
        assert os.readlink(link) == (  # noqa: PTH115
            str(target) + "/" if existing == "normalized-link" else "foreign"
        )


class StartupBoundary:
    """Supply disposable startup effects and observe the real exec boundary."""

    def __init__(
        self, files: ApplianceFiles, failure: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prepare a synthetic appliance without starting external programs."""
        self.files = files
        self.failure = failure
        self.shared = files("/wolf-runtime")
        self.shared.mkdir()
        self.shared.chmod(0o750)
        self.metadata = files("/run/gow-full-x86-session.json")
        self.metadata.parent.mkdir()
        (files.root / "tmp").mkdir()
        self.created_directories: list[Path] = []
        self.connections: list[int] = []
        self.captured_environments: list[dict[str, str]] = []
        self.original_mkdtemp = tempfile.mkdtemp
        self.environment = {
            "PUID": str(os.getuid()),
            "PGID": str(os.getgid()),
            "XDG_RUNTIME_DIR": str(self.shared),
            "WAYLAND_DISPLAY": "wayland-fixture",
            "GOW_SETPRIV": "/fixture/setpriv",
            "GAMESCOPE_WIDTH": "1280",
            "GAMESCOPE_HEIGHT": "720",
            "GOW_FIXTURE_LABEL": "preserved-fixture-label",
        }
        monkeypatch.setattr(runtime, "HERE", files("/assets"))
        monkeypatch.setattr(tempfile, "mkdtemp", self.private_directory)
        monkeypatch.setattr(pwd, "getpwuid", self.existing_user)
        monkeypatch.setattr(shutil, "which", lambda name: "/fixture/" + name)
        monkeypatch.setattr(subprocess, "run", self.startup_command)
        monkeypatch.setattr(os, "execve", self.reject_exec)
        monkeypatch.setattr(os, "environ", self.environment)
        self.protected = self.prepare_conflict()

    def private_directory(self, *, prefix: str, **options: str) -> str:
        """Redirect the API's temporary-directory operand into owned storage."""
        assert options == {"dir": str(Path("/") / "tmp")}
        directory = self.original_mkdtemp(prefix=prefix, dir=self.files.root)
        self.created_directories.append(Path(directory))
        return directory

    @staticmethod
    def existing_user(uid: int) -> pwd.struct_passwd:
        """Model an existing account with the current test identity."""
        return pwd.struct_passwd(
            ("session-user", "x", uid, os.getgid(), "", "/borrowed-home", "/bin/false")
        )

    def startup_command(
        self,
        command: Sequence[str],
        *,
        check: bool,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        """Model loader refresh, settings writes and external state population."""
        del timeout
        assert check
        if command[0] == "/sbin/ldconfig":
            assert "-X" in command
        elif Path(command[0]).name == "batocera-settings-set":
            assert command[1:4] == ["-f", "/boot/batocera-boot.conf", "es.resolution"]
            self.files.file(
                "/boot/batocera-boot.conf", "es.resolution=" + command[4] + "\n"
            )
        elif Path(command[0]).name == "init-state.sh":
            assert env is not None
            self.files.file("/initialized", "state initializer completed\n")
        else:
            pytest.fail(f"Unexpected startup command: {command!r}")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def reject_exec(
        self,
        executable: str,
        arguments: Sequence[str],
        environment: Mapping[str, str],
    ) -> Never:
        """Observe privilege-drop inputs, then refuse the actual process handoff."""
        snapshot = dict(environment)
        self.captured_environments.append(snapshot)
        descriptor = int(snapshot["WAYLAND_SOCKET"])
        self.connections.append(descriptor)
        assert os.get_inheritable(descriptor)
        assert executable == "/fixture/setpriv"
        assert list(arguments) == [
            "/fixture/setpriv",
            "--reuid",
            str(os.getuid()),
            "--regid",
            str(os.getgid()),
            "--groups",
            str(os.getgid()),
            "--",
            str(self.files("/assets/session.sh")),
            "frontend",
            "--windowed",
        ]
        private = Path(snapshot["GOW_CHILD_RUNTIME"])
        assert json.loads(self.metadata.read_text(encoding="utf-8")) == {
            "runtime": str(private),
            "display": ":0",
            "xauthority": str(private / "Xauthority"),
            "puid": os.getuid(),
            "pgid": os.getgid(),
        }
        assert stat.S_IMODE(private.stat().st_mode) == 0o700
        assert stat.S_IMODE(self.metadata.stat().st_mode) == 0o644
        if self.failure == "replacement":
            self.metadata.rename(self.files.root / "displaced-metadata")
            self.metadata.write_bytes(b"foreign replacement metadata")
            private.rename(self.files.root / "displaced-runtime")
            private.mkdir()
            (private / "foreign").write_bytes(b"foreign replacement directory")
        raise OSError(errno.ENOEXEC, "fixture exec refused")

    def prepare_conflict(self) -> Path | None:
        """Install only the foreign object named by the failure scenario."""
        if self.failure == "metadata":
            self.metadata.write_bytes(b"foreign existing metadata")
        elif self.failure == "transient":
            protected = self.files.file("/foreign-transient", "operator-owned\n")
            link = self.files("/var/run/evmapy/merged.keys")
            link.parent.mkdir(parents=True)
            link.symlink_to(protected)
            return protected
        return None

    def invoke_failure(self) -> None:
        """Require the selected failure rather than swallowing an earlier error."""
        if self.failure == "transient":
            with pytest.raises(
                RuntimeError,
                match=r"unexpected transient symlink: .*/evmapy/merged\.keys",
            ):
                runtime.entrypoint(["frontend", "--windowed"])
            return
        expected: dict[str, tuple[type[OSError], int, str]] = {
            "metadata": (FileExistsError, errno.EEXIST, r"\[Errno 17\] File exists"),
            "wayland": (
                FileNotFoundError,
                errno.ENOENT,
                r"\[Errno 2\] No such file or directory",
            ),
            "exec": (OSError, errno.ENOEXEC, r"\[Errno 8\] fixture exec refused"),
            "replacement": (
                OSError,
                errno.ENOEXEC,
                r"\[Errno 8\] fixture exec refused",
            ),
        }
        exception, error_number, message = expected[self.failure]
        with pytest.raises(exception, match=message) as error:
            runtime.entrypoint(["frontend", "--windowed"])
        assert error.value.errno == error_number
        if self.failure in {"exec", "replacement"}:
            assert len(self.captured_environments) == 1

    def assert_transient_cleanup(self) -> None:
        """Check original allocations disappear while foreign replacements remain."""
        assert len(self.created_directories) == 1
        private = self.created_directories[0]
        if self.failure == "replacement":
            assert self.metadata.read_bytes() == b"foreign replacement metadata"
            assert (
                private / "foreign"
            ).read_bytes() == b"foreign replacement directory"
            assert (self.files.root / "displaced-metadata").is_file()
            assert (self.files.root / "displaced-runtime").is_dir()
        else:
            assert not private.exists()
            if self.failure == "metadata":
                assert self.metadata.read_bytes() == b"foreign existing metadata"
            else:
                assert not self.metadata.exists()
        if self.protected is not None:
            assert self.protected.read_text(encoding="utf-8") == "operator-owned\n"
            assert self.files("/var/run/evmapy/merged.keys").is_symlink()

    def assert_exec_cleanup(self) -> None:
        """Check child-only environment changes and closure of connected handles."""
        if self.captured_environments:
            child = self.captured_environments[0]
            assert child["HOME"] == "/userdata/system"
            assert child["USER"] == child["LOGNAME"] == "session-user"
            assert child["GOW_FIXTURE_LABEL"] == "preserved-fixture-label"
            assert child["XDG_RUNTIME_DIR"] == str(self.shared)
            assert "GOW_CHILD_RUNTIME" not in self.environment
            assert "WAYLAND_SOCKET" not in self.environment
        for descriptor in self.connections:
            with pytest.raises(
                OSError, match=r"\[Errno 9\] Bad file descriptor"
            ) as error:
                os.fstat(descriptor)
            assert error.value.errno == errno.EBADF


@pytest.mark.parametrize(
    "failure", ["metadata", "transient", "wayland", "exec", "replacement"]
)
def test_entrypoint_failure_reclaims_only_owned_private_transients(
    failure: str, files: ApplianceFiles, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revoke startup allocations without touching Wolf or replacement inodes."""
    boundary = StartupBoundary(files, failure, monkeypatch)
    shared = boundary.shared
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.settimeout(1)
        if failure in {"exec", "replacement"}:
            server.bind(str(shared / "wayland-fixture"))
            server.listen(1)
        shared_identity = shared.stat().st_ino, stat.S_IMODE(shared.stat().st_mode)
        boundary.invoke_failure()
        if failure in {"exec", "replacement"}:
            accepted, _ = server.accept()
            with accepted:
                accepted.settimeout(1)
                assert accepted.recv(1) == b""
        assert (
            shared.stat().st_ino,
            stat.S_IMODE(shared.stat().st_mode),
        ) == shared_identity
    assert (
        files("/boot/batocera-boot.conf").read_text(encoding="utf-8")
        == "es.resolution=1280x720\n"
    )
    assert (
        files("/initialized").read_text(encoding="utf-8")
        == "state initializer completed\n"
    )
    boundary.assert_transient_cleanup()
    boundary.assert_exec_cleanup()


@pytest.mark.parametrize("failure", ["", "remove", "unrelated"])
def test_hotkeys_ignore_only_disappeared_add_nodes_and_continue_processing(
    failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skip a vanished forwarded node, not another action or missing dependency."""
    vanished = tmp_path / "vanished-event"
    present = tmp_path / "present-event"
    present.write_text("consumer-visible mapping", encoding="utf-8")
    unrelated = tmp_path / "missing-context"
    processed: list[str] = []

    class Device:
        def __init__(self, path: Path) -> None:
            self.device_node = str(path)

    class ExternalDaemon:
        def __init__(self, *, permanent: bool) -> None:
            assert permanent

        def handle_actions(
            self, action: str, device: runtime.StockInputDevice
        ) -> object:
            del self, action
            path = unrelated if failure == "unrelated" else Path(device.device_node)
            contents = path.read_text(encoding="utf-8")
            processed.append(contents)
            return contents

        def run(self) -> None:
            handler = getattr(self, STOCK_ACTION_NAME)
            handler("remove" if failure == "remove" else "add", Device(vanished))
            handler("add", Device(present))

    setattr(ExternalDaemon, STOCK_ACTION_NAME, ExternalDaemon.handle_actions)

    def external_program(path: str) -> dict[str, object]:
        assert path == "/fixture/hotkeygen"
        return {"Daemon": ExternalDaemon}

    monkeypatch.setattr(shutil, "which", lambda _name: "/fixture/hotkeygen")
    monkeypatch.setattr(runpy, "run_path", external_program)
    if failure:
        with pytest.raises(FileNotFoundError) as error:
            runtime.run_hotkeys()
        assert error.value.filename == str(
            unrelated if failure == "unrelated" else vanished
        )
        assert processed == []
        assert capsys.readouterr().out == ""
    else:
        runtime.run_hotkeys()
        assert processed == ["consumer-visible mapping"]
        assert (
            capsys.readouterr().out
            == f"gow-full-x86: ignoring unmounted input node {vanished}\n"
        )


@pytest.mark.parametrize(
    "damage", ["symlink", "hardlink", "fifo", "parent-link", "stock-link"]
)
def test_marked_state_refuses_unsafe_generated_database_without_leaking_descriptors(
    damage: str, files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Retain foreign files and the successful marker when a later path is unsafe."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    state.run()
    marker = state.marker.read_bytes(), state.marker.stat().st_ino
    generated = state.final / "system/.gow-full-x86-generated"
    database = generated / "duckstation/gamecontrollerdb.txt"
    outside = files.file("/foreign/controller-db", "operator database\n")
    if damage == "parent-link":
        generated.rename(state.final / "system/displaced-generated")
        generated.symlink_to(outside.parent)
    elif damage == "stock-link":
        destination = files("/usr/share/duckstation/resources/gamecontrollerdb.txt")
        destination.unlink()
        destination.symlink_to(outside)
    else:
        database.unlink()
        if damage == "symlink":
            database.symlink_to(outside)
        elif damage == "hardlink":
            os.link(outside, database)
        else:
            os.mkfifo(database, 0o600)
    descriptors = set(Path("/proc/self/fd").iterdir())
    with pytest.raises(RuntimeError, match="controller database"):
        state.run()
    assert set(Path("/proc/self/fd").iterdir()) == descriptors
    assert outside.read_text(encoding="utf-8") == "operator database\n"
    assert (state.marker.read_bytes(), state.marker.stat().st_ino) == marker
    assert (population.extractions, population.populations) == (1, 1)
    if damage == "parent-link":
        assert generated.is_symlink()
    elif damage == "stock-link":
        assert (
            files("/usr/share/duckstation/resources/gamecontrollerdb.txt").readlink()
            == outside
        )
    elif damage == "fifo":
        assert stat.S_ISFIFO(database.lstat().st_mode)
    elif damage == "symlink":
        assert database.readlink() == outside
    else:
        assert database.stat().st_ino == outside.stat().st_ino
        assert outside.stat().st_nlink == 2


@pytest.mark.parametrize("damage", ["link", "directory"])
def test_machine_identity_destination_conflict_keeps_interrupted_state_unmarked(
    damage: str, files: ApplianceFiles, population: PopulationBoundary
) -> None:
    """Never erase a foreign identity link or directory while publishing state."""
    destination = files("/etc/machine-id")
    destination.unlink()
    foreign = files.file("/foreign/machine-id", "foreign machine identity\n")
    if damage == "link":
        destination.symlink_to(foreign)
    else:
        destination.mkdir()
        (destination / "keep").write_bytes(b"foreign directory")
    identity = destination.lstat().st_ino
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    with pytest.raises(RuntimeError, match="machine-id"):
        state.run()
    assert destination.lstat().st_ino == identity
    assert foreign.read_text(encoding="utf-8") == "foreign machine identity\n"
    assert not state.marker.exists()
    assert state.seed.is_dir()
    assert not state.work.exists()
    assert (state.final / "system/machine-id").read_text(
        encoding="utf-8"
    ) == "stable-fixture-identity\n"
    assert (population.extractions, population.populations) == (1, 1)
    if damage == "directory":
        assert (destination / "keep").read_bytes() == b"foreign directory"


@pytest.mark.parametrize("failure", ["existing-partial", "fsync"])
def test_marker_publication_failure_keeps_installed_state_uncommitted(
    failure: str,
    files: ApplianceFiles,
    population: PopulationBoundary,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interrupted final commit never becomes a reusable successful home."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    partial = files.home / ".gow-full-x86-state.json.partial"
    original_fsync = os.fsync
    if failure == "existing-partial":
        partial.write_bytes(b"foreign partial marker")
    else:

        def reject_marker_flush(descriptor: int) -> None:
            if Path(f"/proc/self/fd/{descriptor}").readlink() == partial:
                raise OSError(errno.ENOSPC, "owned marker flush failed")
            original_fsync(descriptor)

        monkeypatch.setattr(os, "fsync", reject_marker_flush)
    expected_errno = errno.EEXIST if failure == "existing-partial" else errno.ENOSPC
    expected_message = (
        r"\[Errno 17\] File exists"
        if failure == "existing-partial"
        else r"\[Errno 28\] owned marker flush failed"
    )
    with pytest.raises(OSError, match=expected_message) as error:
        state.run()
    assert error.value.errno == expected_errno
    assert not state.marker.exists()
    assert partial.is_file()
    if failure == "existing-partial":
        assert partial.read_bytes() == b"foreign partial marker"
    else:
        assert json.loads(partial.read_text(encoding="utf-8")) == {
            "release": "43.1",
            "puid": os.getuid(),
            "pgid": os.getgid(),
        }
    assert not state.work.exists()
    assert (
        state.seed / "roms/new-system/subdir/demo.rom"
    ).read_bytes() == b"legal fixture\n"
    assert (state.final / "system/machine-id").read_text(
        encoding="utf-8"
    ) == "stable-fixture-identity\n"
    with pytest.raises(RuntimeError, match="interrupted or unrelated initialization"):
        state.run()
    assert (population.extractions, population.populations) == (1, 1)


def test_marked_state_with_unowned_home_is_refused_before_reinitialization(
    files: ApplianceFiles,
    population: PopulationBoundary,
) -> None:
    """A matching marker identity cannot authorize another account's filesystem."""
    state = runtime.StateInitializer(os.getuid(), os.getgid(), files.home)
    state.run()
    other_uid = os.getuid() + 1
    state.marker.write_text(
        json.dumps({"release": "43.1", "puid": other_uid, "pgid": os.getgid()}),
        encoding="utf-8",
    )
    before = state.marker.read_bytes(), (state.final / "system/machine-id").read_bytes()
    other = runtime.StateInitializer(other_uid, os.getgid(), files.home)
    with pytest.raises(RuntimeError, match="state ownership mismatch"):
        other.run()
    assert (
        state.marker.read_bytes(),
        (state.final / "system/machine-id").read_bytes(),
    ) == before
    assert (population.extractions, population.populations) == (1, 1)
