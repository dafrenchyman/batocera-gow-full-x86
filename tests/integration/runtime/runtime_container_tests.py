"""Disposable-container tests. Never run this module on the host."""

import json
import os
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from batocera_gow.runtime import runtime

pytestmark = pytest.mark.runtime
SOURCE = Path("/project")
ASSETS = SOURCE / "build-assets/runtime"


def command(*args: str) -> None:
    """Run a fixture command and fail on unsuccessful completion."""
    # Only fixed argv from the isolated fixture reaches this helper.
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)  # noqa: S603


def wait_for(predicate: Callable[[], bool], timeout: float = 5) -> None:
    """Wait at most timeout seconds for a fixture-owned process condition."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            msg = "fixture condition timed out"
            raise AssertionError(msg)
        time.sleep(0.03)


def executable(path: Path, content: str) -> str:
    """Create an executable fixture script and return its absolute path."""
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def snapshot(root: Path) -> dict[str, tuple[int, int, int, bytes | None]]:
    """Record ownership, permissions and file contents beneath a fixture root."""
    result = {}
    for path in [root, *root.rglob("*")]:
        info = path.lstat()
        result[str(path.relative_to(root))] = (
            info.st_uid,
            info.st_gid,
            stat.S_IMODE(info.st_mode),
            path.read_bytes() if path.is_file() else None,
        )
    return result


class TestState:
    """Exercise initialization against disposable, real mount boundaries."""

    # The autouse state fixture initializes these after checking container isolation.
    # Constructors must not allocate mounts or fixture paths during collection.
    stack: ExitStack  # pyright: ignore[reportUninitializedInstanceVariable]
    base: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    home: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    final: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    roms: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    before: dict[  # pyright: ignore[reportUninitializedInstanceVariable]
        str, tuple[int, int, int, bytes | None]
    ]
    udev_before: dict[  # pyright: ignore[reportUninitializedInstanceVariable]
        str, tuple[int, int, int, bytes | None]
    ]
    data: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    uid: int  # pyright: ignore[reportUninitializedInstanceVariable]
    gid: int  # pyright: ignore[reportUninitializedInstanceVariable]
    resources: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    resource_source: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    database: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    resource_before: dict[  # pyright: ignore[reportUninitializedInstanceVariable]
        str, tuple[int, int, int, bytes | None]
    ]

    @pytest.fixture(autouse=True)
    def state(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Iterator[None]:
        """Own mounted resources across setup failures and test execution."""
        if (
            not Path("/.dockerenv").exists()
            or os.environ.get("GOW_RUNTIME_FIXTURE") != "1"
        ):
            pytest.skip("requires the isolated mount fixture container")
        with ExitStack() as stack:
            self.stack = stack
            self.base = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            self.prepare_library_mounts()
            self.prepare_stock_seed()
            self.prepare_resource_mount()
            monkeypatch.setattr(runtime, "HERE", self.base)
            yield

    def prepare_library_mounts(self) -> None:
        """Mount private home and readonly libraries, registering each unmount."""
        self.home = Path("/home/retro")
        self.home.mkdir(parents=True, exist_ok=True)
        command("mount", "-t", "tmpfs", "tmpfs", str(self.home))
        self.stack.callback(command, "umount", str(self.home))
        self.stack.callback(self.remove_userdata_link)
        self.final = self.home / "userdata"
        self.final.mkdir()
        (self.home / "udev").mkdir()
        (self.home / "udev/untouched").write_text(
            "Wolf-owned fake database", encoding="utf-8"
        )
        self.roms = self.base / "ROMs"
        (self.roms / "bioses").mkdir(parents=True)
        (self.roms / "game.rom").write_text("legal fixture", encoding="utf-8")
        (self.roms / "bioses/bios.bin").write_text("BIOS fixture", encoding="utf-8")
        for name, source in (("roms", self.roms), ("bios", self.roms / "bioses")):
            target = self.final / name
            target.mkdir()
            command("mount", "--bind", str(source), str(target))
            self.stack.callback(command, "umount", str(target))
            command("mount", "-o", "remount,bind,ro", str(target))
        self.before = snapshot(self.roms)
        self.udev_before = snapshot(self.home / "udev")

    def prepare_stock_seed(self) -> None:
        """Create untouched stock population inputs and a SHARE seed archive."""
        init = Path("/etc/init.d/S12populateshare")
        init.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            SOURCE / "tests/integration/runtime/stock-S12populateshare", init
        )
        self.data = Path("/usr/share/batocera/datainit")
        if self.data.exists():
            shutil.rmtree(self.data)
        for directory in (
            "roms/mame/mame2003",
            "roms/fixture-system",
            "bios",
            "decorations",
            "system/configs/emulationstation",
        ):
            (self.data / directory).mkdir(parents=True, exist_ok=True)
        (self.data / "roms/fixture-system/_info.txt").write_text(
            "stock game defaults", encoding="utf-8"
        )
        (self.data / "bios/stock-bios.txt").write_text(
            "stock BIOS defaults", encoding="utf-8"
        )
        (self.data / "decorations/readme.txt").write_text(
            "stock decorations", encoding="utf-8"
        )
        (self.data / "system/batocera.conf").write_text(
            "system.language=en_US\n", encoding="utf-8"
        )
        Path("/usr/share/batocera/batocera.version").write_text(
            "43.1 2026/05/29\n", encoding="utf-8"
        )
        Path("/boot").mkdir(exist_ok=True)
        seed = self.base / "share"
        (seed / "roms").mkdir(parents=True)
        (seed / "bios").mkdir()
        (seed / "roms/share-only.rom").write_text("stock SHARE ROM", encoding="utf-8")
        (seed / "bios/share-only.bios").write_text("stock SHARE BIOS", encoding="utf-8")
        (seed / "share-only.txt").write_text("preserve me", encoding="utf-8")
        command(
            "tar",
            "--numeric-owner",
            "--acls",
            "--xattrs",
            "-cpf",
            str(self.base / "stock-share.tar"),
            "-C",
            str(seed),
            ".",
        )

    def prepare_resource_mount(self) -> None:
        """Mount a private stock resource tree with root-owned original files."""
        name = "es_systems_gow_duckstation.cfg"
        shutil.copyfile(ASSETS / name, self.base / name)
        self.uid, self.gid = 1234, 1235
        self.resources = Path("/usr/share/duckstation/resources")
        self.resources.mkdir(parents=True, exist_ok=True)
        self.resource_source = self.base / "resources"
        self.resource_source.mkdir(mode=0o755)
        (self.resource_source / "stock-resource").write_bytes(b"unchanged stock")
        command("mount", "--bind", str(self.resource_source), str(self.resources))
        self.stack.callback(command, "umount", str(self.resources))
        self.database = self.resources / "gamecontrollerdb.txt"
        assert not self.database.exists()
        assert not self.database.is_symlink()
        self.resource_before = snapshot(self.resources)

    @staticmethod
    def remove_userdata_link() -> None:
        """Remove only the userdata symlink created inside the fixture container."""
        userdata = Path("/userdata")
        if userdata.is_symlink():
            userdata.unlink()

    def initializer(self) -> runtime.StateInitializer:
        """Create the initializer for the fixture's selected app identity."""
        return runtime.StateInitializer(self.uid, self.gid)

    def unchanged_external(self) -> None:
        """Verify external library and Wolf-owned udev state remain untouched."""
        assert snapshot(self.roms) == self.before
        assert snapshot(self.home / "udev") == self.udev_before

    def replace_directory_as_app(self, directory: Path, outside: Path) -> Path:
        """Substitute an ancestor using only the initialized app's privileges."""
        # Moving a root-owned 0700 directory across parents requires write
        # access to it; renaming within its app-owned parent does not.
        displaced = directory.with_name(directory.name + "-displaced")
        command(
            "setpriv",
            f"--reuid={self.uid}",
            f"--regid={self.gid}",
            "--clear-groups",
            sys.executable,
            "-c",
            "import os,sys\nos.rename(sys.argv[1],sys.argv[2])\n"
            "os.symlink(sys.argv[3],sys.argv[1])\n",
            str(directory),
            str(displaced),
            str(outside),
        )
        return displaced

    def test_startup_installs_partial_psx_command_and_repeated_start_is_noop(
        self,
    ) -> None:
        """Startup installs partial psx command and repeated start is noop."""
        self.initializer().run()
        destination = (
            self.final
            / "system/configs/emulationstation/es_systems_gow_duckstation.cfg"
        )
        assert (
            destination.read_bytes()
            == (ASSETS / "es_systems_gow_duckstation.cfg").read_bytes()
        )
        first = destination.stat()
        assert (first.st_uid, first.st_gid) == (self.uid, self.gid)
        self.initializer().run()
        current = destination.stat()
        assert (first.st_ino, first.st_mtime_ns) == (
            current.st_ino,
            current.st_mtime_ns,
        )
        self.unchanged_external()

    def test_startup_preserves_user_psx_commands_instead_of_choosing_overlay_order(
        self,
    ) -> None:
        """Startup preserves user psx commands instead of choosing overlay order."""
        self.initializer().run()
        directory = self.final / "system/configs/emulationstation"
        destination = directory / "es_systems_gow_duckstation.cfg"
        destination.unlink()
        custom = directory / "es_systems_user.cfg"
        custom.write_text(
            "<systemList><system><name>psx</name><command>custom</command></system></systemList>",
            encoding="utf-8",
        )
        os.chown(custom, self.uid, self.gid)
        before = custom.read_bytes()
        self.initializer().run()
        assert not destination.exists()
        assert custom.read_bytes() == before
        custom.unlink()
        destination.write_bytes(b"user modified")
        os.chown(destination, self.uid, self.gid)
        self.initializer().run()
        assert destination.read_bytes() == b"user modified"
        self.unchanged_external()

    def test_override_directory_substitution_never_chowns_or_writes_foreign_target(
        self,
    ) -> None:
        """Override directory substitution never chowns or writes foreign target."""
        self.initializer().run()
        directory = self.final / "system/configs/emulationstation"
        shutil.rmtree(directory)
        outside = self.base / "foreign"
        outside.mkdir()
        (outside / "sentinel").write_bytes(b"foreign")
        before = snapshot(outside)
        chown = os.fchown
        displaced: list[Path] = []

        def substitute(descriptor: int, uid: int, gid: int) -> None:
            info = os.fstat(descriptor)
            if (
                not displaced
                and directory.exists()
                and info.st_ino == directory.stat().st_ino
            ):
                displaced.append(self.replace_directory_as_app(directory, outside))
            chown(descriptor, uid, gid)

        with (
            patch.object(os, "fchown", side_effect=substitute),
            pytest.raises(NotADirectoryError),
        ):
            self.initializer().install_duckstation_override()
        assert displaced
        assert snapshot(outside) == before
        assert directory.is_symlink()
        assert list(displaced[0].iterdir()) == []
        self.unchanged_external()

    def test_catalog_publication_source_cannot_be_substituted_by_the_app(self) -> None:
        """Catalog publication source cannot be substituted by the app."""
        self.initializer().run()
        directory = self.final / "system/configs/emulationstation"
        destination = directory / "es_systems_gow_duckstation.cfg"
        destination.unlink()
        link = os.link
        attempted: list[Path] = []

        def attack(
            source: str,
            target: str,
            *,
            src_dir_fd: int | None = None,
            dst_dir_fd: int | None = None,
            follow_symlinks: bool = True,
        ) -> None:
            staging = Path(str(Path(f"/proc/self/fd/{src_dir_fd}").readlink()))
            attempted.append(staging)
            command(
                "setpriv",
                f"--reuid={self.uid}",
                f"--regid={self.gid}",
                "--clear-groups",
                sys.executable,
                "-c",
                "import os,sys\n"
                "try: os.unlink(sys.argv[1])\n"
                "except PermissionError: pass\n"
                "else: raise SystemExit('app could substitute publication source')\n",
                str(staging / source),
            )
            link(
                source,
                target,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )

        with patch.object(os, "link", side_effect=attack):
            self.initializer().install_duckstation_override()
        assert len(attempted) == 1
        assert not attempted[0].exists()
        assert (
            destination.read_bytes()
            == (ASSETS / "es_systems_gow_duckstation.cfg").read_bytes()
        )
        assert destination.stat().st_nlink == 1
        self.unchanged_external()

    def test_installed_catalog_uses_packaged_wrapper_after_final_config_is_generated(
        self,
    ) -> None:
        """Execute installed catalog assets across launcher and consumer seams."""
        self.initializer().run()
        packaged = Path("/opt/gow-full-x86")
        launcher = Path("/usr/bin/emulatorlauncher")
        consumer = Path("/usr/bin/duckstation-qt")
        for path in (packaged, launcher, consumer):
            assert not path.exists(), "Fixture must never replace installed stock paths"
        packaged.mkdir()
        self.stack.callback(shutil.rmtree, packaged)
        shutil.copyfile(
            ASSETS / "duckstation_wrapper.py", packaged / "duckstation_wrapper.py"
        )
        package = packaged / "batocera_gow"
        package.mkdir()
        installed = Path(runtime.__file__).parent
        shutil.copyfile(installed.parent / "__init__.py", package / "__init__.py")
        shutil.copytree(installed, package / "runtime")
        wrappers = packaged / "emulator-wrappers"
        wrappers.mkdir()
        shutil.copyfile(
            ASSETS / "emulator-wrappers/duckstation-qt",
            wrappers / "duckstation-qt",
        )
        (wrappers / "duckstation-qt").chmod(0o755)
        launcher.write_text(
            "#!/usr/bin/python3\n"
            "import os\nfrom pathlib import Path\n"
            "p=Path('/userdata/system/configs/duckstation/settings.ini')\n"
            "p.parent.mkdir(parents=True,exist_ok=True)\n"
            "p.write_text('[GPU]\\nRenderer='+os.environ['GOW_FIXTURE_RENDERER']+'\\n')\n"
            "os.execvp('duckstation-qt',"
            "['duckstation-qt','-batch','-nogui','--','fixture disc.chd'])\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        self.stack.callback(launcher.unlink)
        consumer.write_text(
            "#!/usr/bin/python3\n"
            "import json,os,sys\nfrom pathlib import Path\n"
            "Path(os.environ['GOW_FIXTURE_WITNESS']).write_text(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        consumer.chmod(0o755)
        self.stack.callback(consumer.unlink)
        destination = (
            self.final
            / "system/configs/emulationstation/es_systems_gow_duckstation.cfg"
        )
        # The initializer copied this repository-owned XML asset into fixture state.
        command_text = ET.fromstring(destination.read_bytes()).findtext(  # noqa: S314
            "system/command"
        )
        assert command_text is not None
        for placeholder, value in {
            "CONTROLLERSCONFIG": "",
            "SYSTEM": "psx",
            "ROM": shlex.quote("fixture disc.chd"),
            "GAMEINFOXML": "fixture.xml",
            "SYSTEMNAME": "PlayStation",
        }.items():
            command_text = command_text.replace("%" + placeholder + "%", value)
        witness = self.final / "wrapper-witness.json"
        for renderer in ("Vulkan", "OpenGL"):
            # Execute only the repository catalog's substituted fixture command.
            completed = subprocess.run(  # noqa: S603
                [
                    "/usr/bin/setpriv",
                    f"--reuid={self.uid}",
                    f"--regid={self.gid}",
                    "--clear-groups",
                    "/bin/sh",
                    "-c",
                    command_text,
                ],
                env={
                    **os.environ,
                    "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
                    "DISPLAY": ":65535",
                    "GOW_FIXTURE_RENDERER": renderer,
                    "GOW_FIXTURE_WITNESS": str(witness),
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if renderer == "Vulkan":
                assert completed.returncode == 0, completed.stderr
                assert json.loads(witness.read_text(encoding="utf-8")) == [
                    "-batch",
                    "-nogui",
                    "--",
                    "fixture disc.chd",
                ]
                witness.unlink()
            else:
                assert completed.returncode != 0
                assert "OpenGL launch refused" in completed.stderr
                assert not witness.exists(), (
                    "Failed discovery must not exec uncorrected"
                )
        self.unchanged_external()

    def test_uid1000_stock_writer_keeps_generated_database_in_userdata(self) -> None:
        """Uid1000 stock writer keeps generated database in userdata."""
        self.uid = self.gid = 1000
        self.base.chmod(0o755)
        package = self.base / "configgen"
        package.mkdir()
        (package / "__init__.py").touch()
        with tarfile.open("/stock-root.tar") as archive:
            for name in (
                "controller.py",
                "input.py",
                "exceptions.py",
                "batoceraPaths.py",
            ):
                member = archive.getmember(
                    "./usr/lib/python3.12/site-packages/configgen/" + name
                )
                assert member.isfile()
                assert member.size < 65536
                stream = archive.extractfile(member)
                assert stream is not None
                with stream:
                    (package / name).write_bytes(stream.read(65536))
        writer = self.base / "write-controller-db.py"
        writer.write_text(
            "import os\n"
            "from configgen.controller import Controller, write_sdl_controller_db\n"
            "from configgen.input import Input\n"
            "assert os.getuid() == os.getgid() == 1000\n"
            "controller = Controller(name='fixture', type='joystick', "
            "guid='fixture-guid', player_number=1, index=0, "
            "real_name='Fixture Pad', device_path='/dev/null', "
            "button_count=1, hat_count=0, axis_count=0, inputs_={"
            "'start': Input(name='start', type='button', id='7', value='1')})\n"
            "write_sdl_controller_db([controller], "
            "'/usr/share/duckstation/resources/gamecontrollerdb.txt')\n",
            encoding="utf-8",
        )
        arguments = [
            "setpriv",
            "--reuid=1000",
            "--regid=1000",
            "--clear-groups",
            sys.executable,
            str(writer),
        ]
        # The real stock writer cannot create its output in root:root0755.
        # Fixed argv runs the unchanged stock writer with disposable app identity.
        refused = subprocess.run(  # noqa: S603
            arguments,
            capture_output=True,
            check=False,
        )
        assert refused.returncode != 0
        assert b"PermissionError" in refused.stderr
        self.initializer().run()
        parent_before = self.resources.stat()
        command(*arguments)
        expected = b"fixture-guid,Fixture Pad,platform:Linux,start:b7,"
        assert self.database.read_bytes() == expected
        generated = self.database.resolve(strict=True)
        assert generated.is_relative_to(self.final)
        assert (generated.stat().st_uid, generated.stat().st_gid) == (1000, 1000)
        original = (generated.stat().st_ino, generated.stat().st_mtime_ns)
        self.initializer().run()
        assert self.database.read_bytes() == expected
        assert (generated.stat().st_ino, generated.stat().st_mtime_ns) == original
        assert (parent_before.st_uid, parent_before.st_gid) == (0, 0)
        assert stat.S_IMODE(parent_before.st_mode) == 0o755
        parent_after = self.resources.stat()
        assert (parent_after.st_uid, parent_after.st_gid, parent_after.st_mode) == (
            parent_before.st_uid,
            parent_before.st_gid,
            parent_before.st_mode,
        )
        assert {
            key: value
            for key, value in snapshot(self.resources).items()
            if key != "gamecontrollerdb.txt"
        } == self.resource_before
        self.unchanged_external()

    def test_existing_stock_destination_collisions_are_preserved(self) -> None:
        """Existing stock destination collisions are preserved."""
        self.initializer().run()
        target = self.database.resolve(strict=True)
        self.database.unlink()
        for kind in ("file", "directory", "symlink", "foreign-link"):
            if kind == "file":
                self.database.write_bytes(b"preserve existing stock file")
            elif kind == "directory":
                self.database.mkdir()
                (self.database / "keep").write_bytes(b"preserve directory")
            elif kind == "symlink":
                self.database.symlink_to(self.resources / "stock-resource")
            else:
                self.database.symlink_to(target)
                os.lchown(self.database, self.uid, self.gid)
            info = self.database.lstat()
            with pytest.raises(RuntimeError):
                self.initializer().run()
            assert self.database.lstat().st_ino == info.st_ino
            if kind == "file":
                assert self.database.read_bytes() == b"preserve existing stock file"
                self.database.unlink()
            elif kind == "directory":
                assert (self.database / "keep").read_bytes() == b"preserve directory"
                (self.database / "keep").unlink()
                self.database.rmdir()
            else:
                expected = (
                    self.resources / "stock-resource" if kind == "symlink" else target
                )
                assert str(self.database.readlink()) == str(expected)
                assert self.database.lstat().st_uid == info.st_uid
                self.database.unlink()
            assert target.read_bytes() == b""
        self.unchanged_external()

    def test_generated_database_symlink_and_hardlink_escapes_are_preserved(
        self,
    ) -> None:
        """Generated database symlink and hardlink escapes are preserved."""
        self.initializer().run()
        target = self.database.resolve(strict=True)
        target.unlink()
        outside = self.home / "keep"
        outside.write_bytes(b"unrelated user data")
        os.chown(outside, self.uid, self.gid)
        for kind in ("symlink", "hardlink", "directory", "fifo", "foreign-owner"):
            if kind == "symlink":
                target.symlink_to(outside)
            elif kind == "hardlink":
                os.link(outside, target)
            elif kind == "directory":
                target.mkdir()
            elif kind == "fifo":
                os.mkfifo(target)
            else:
                target.write_bytes(b"foreign file")
            info = target.lstat()
            with pytest.raises(RuntimeError):
                self.initializer().run()
            assert target.lstat().st_ino == info.st_ino
            assert outside.read_bytes() == b"unrelated user data"
            if kind == "directory":
                target.rmdir()
            else:
                target.unlink()
        self.unchanged_external()

    def test_generated_database_directory_escape_is_preserved(self) -> None:
        """Generated database directory escape is preserved."""
        self.initializer().run()
        target = self.database.resolve(strict=True)
        outside = self.home / "keep"
        outside.mkdir()
        sentinel = outside / "gamecontrollerdb.txt"
        sentinel.write_bytes(b"unrelated user data")
        for directory in (target.parent, target.parent.parent):
            original = self.home / "original"
            directory.rename(original)
            directory.symlink_to(outside)
            with pytest.raises(RuntimeError):
                self.initializer().run()
            assert directory.is_symlink()
            assert sentinel.read_bytes() == b"unrelated user data"
            directory.unlink()
            original.rename(directory)
        self.unchanged_external()

    def test_created_directory_substitution_does_not_chown_foreign_targets(
        self,
    ) -> None:
        """Created directory substitution does not chown foreign targets."""
        self.initializer().run()
        target = self.database.resolve(strict=True)
        generated = target.parent.parent
        real_mkdir = os.mkdir
        for name in (generated.name, target.parent.name):
            shutil.rmtree(generated)
            outside = self.base / ("foreign-" + name)
            outside.mkdir()
            (outside / "gamecontrollerdb.txt").write_bytes(b"foreign database")
            before = snapshot(outside)
            directory = generated if name == generated.name else target.parent
            displaced: Path | None = None

            def replace_after_creation(
                path: str | os.PathLike[str],
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
                context: tuple[str, Path, Path] = (name, directory, outside),
            ) -> None:
                name, directory, outside = context
                nonlocal displaced
                real_mkdir(path, mode, dir_fd=dir_fd)
                if Path(path).name == name:
                    displaced = self.replace_directory_as_app(directory, outside)

            descriptors = set(Path("/proc/self/fd").iterdir())
            try:
                with (
                    patch.object(os, "mkdir", replace_after_creation),
                    pytest.raises(RuntimeError),
                ):
                    self.initializer().prepare_generated_controller_db()
                assert displaced is not None
                assert directory.is_symlink()
                assert snapshot(outside) == before
                assert set(Path("/proc/self/fd").iterdir()) == descriptors
            finally:
                if displaced is not None:
                    directory.unlink()
                    displaced.rename(directory)
        self.unchanged_external()

    def test_opened_ancestor_substitution_cannot_redirect_root_file_creation(
        self,
    ) -> None:
        """Opened ancestor substitution cannot redirect root file creation."""
        self.initializer().run()
        target = self.database.resolve(strict=True)
        real_open = os.open
        for directory in (
            self.final / "system",
            target.parent.parent,
            target.parent,
        ):
            target.unlink()
            outside = self.base / ("foreign-" + directory.name)
            outside_target = outside / target.relative_to(directory)
            outside_target.parent.mkdir(parents=True, exist_ok=True)
            before = snapshot(outside)
            displaced: Path | None = None

            def replace_before_creation(
                path: str | os.PathLike[str],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
                context: tuple[Path, Path] = (directory, outside),
            ) -> int:
                directory, outside = context
                nonlocal displaced
                if Path(path).name == target.name and flags & os.O_CREAT:
                    displaced = self.replace_directory_as_app(directory, outside)
                return real_open(path, flags, mode, dir_fd=dir_fd)

            descriptors = set(Path("/proc/self/fd").iterdir())
            try:
                with (
                    patch.object(os, "open", replace_before_creation),
                    pytest.raises(RuntimeError),
                ):
                    self.initializer().prepare_generated_controller_db()
                assert displaced is not None
                assert directory.is_symlink()
                assert snapshot(outside) == before
                assert set(Path("/proc/self/fd").iterdir()) == descriptors
            finally:
                if displaced is not None:
                    directory.unlink()
                    displaced.rename(directory)
        self.unchanged_external()

    def test_generated_database_preparation_closes_descriptors_on_success(self) -> None:
        """Generated database preparation closes descriptors on success."""
        self.initializer().run()
        descriptors = set(Path("/proc/self/fd").iterdir())
        self.initializer().prepare_generated_controller_db()
        assert set(Path("/proc/self/fd").iterdir()) == descriptors
        target = self.database.resolve(strict=True)
        target.unlink()
        self.initializer().prepare_generated_controller_db()
        assert set(Path("/proc/self/fd").iterdir()) == descriptors
        assert target.read_bytes() == b""
        self.unchanged_external()

    def test_unsafe_stock_directory_is_refused_without_permission_changes(self) -> None:
        """Unsafe stock directory is refused without permission changes."""
        self.initializer().run()
        for uid, gid, mode in ((self.uid, self.gid, 0o755), (0, 0, 0o777)):
            os.chown(self.resources, uid, gid)
            self.resources.chmod(mode)
            with pytest.raises(RuntimeError):
                self.initializer().run()
            info = self.resources.stat()
            assert (info.st_uid, info.st_gid) == (uid, gid)
            assert stat.S_IMODE(info.st_mode) == mode
        self.unchanged_external()

    def test_stock_initializer_stages_and_preserves_every_seed(self) -> None:
        """Stock initializer stages and preserves every seed."""
        self.initializer().run()
        marker = json.loads(
            (self.home / ".gow-full-x86-state.json").read_text(encoding="utf-8")
        )
        assert marker == {"release": "43.1", "puid": self.uid, "pgid": self.gid}
        assert (self.final / "share-only.txt").read_text(
            encoding="utf-8"
        ) == "preserve me"
        assert (self.home / ".gow-full-x86-stock-seed/roms/share-only.rom").read_text(
            encoding="utf-8"
        ) == "stock SHARE ROM"
        assert (self.home / ".gow-full-x86-stock-seed/bios/share-only.bios").read_text(
            encoding="utf-8"
        ) == "stock SHARE BIOS"
        assert (
            self.home / ".gow-full-x86-stock-seed/roms/fixture-system/_info.txt"
        ).exists()
        assert str(Path("/userdata").readlink()) == str(self.final)
        assert (self.final / "system/machine-id").read_text(encoding="utf-8").strip()
        assert (self.final / "system").stat().st_uid == self.uid
        self.unchanged_external()
        settings = self.final / "system/configs/emulationstation/es_settings.cfg"
        settings.write_text("changed preference", encoding="utf-8")
        original_stat = (settings.stat().st_ino, settings.stat().st_mtime_ns)
        self.initializer().run()
        assert settings.read_text(encoding="utf-8") == "changed preference"
        assert (settings.stat().st_ino, settings.stat().st_mtime_ns) == original_stat
        self.unchanged_external()

    def test_explicit_zero_identity_is_not_defaulted(self) -> None:
        """Explicit zero identity is not defaulted."""
        self.uid = self.gid = 0
        self.initializer().run()
        assert (
            json.loads(
                (self.home / ".gow-full-x86-state.json").read_text(encoding="utf-8")
            )["puid"]
            == 0
        )
        self.initializer().run()
        self.unchanged_external()

    def test_absent_optional_es_defaults_do_not_prevent_first_run(self) -> None:
        """Absent optional es defaults do not prevent first run."""
        self.initializer().run()
        assert not (
            self.final / "system/configs/emulationstation/es_settings.cfg"
        ).exists()
        assert (self.final / "system/batocera.conf").read_text(
            encoding="utf-8"
        ) == "system.language=en_US\n"
        assert (self.home / ".gow-full-x86-state.json").is_file()
        self.initializer().run()
        self.unchanged_external()

    def test_required_configuration_copy_failure_cannot_publish_marker(self) -> None:
        """Required configuration copy failure cannot publish marker."""
        bindir = self.base / "bin"
        bindir.mkdir()
        executable(
            bindir / "cp",
            "#!/bin/sh\nfor argument; do\n"
            ' case "$argument" in */datainit/system/batocera.conf) '
            'exit 29;; esac\ndone\nexec /usr/bin/cp "$@"\n',
        )
        old = os.environ["PATH"]
        os.environ["PATH"] = str(bindir) + ":" + old
        try:
            with pytest.raises(RuntimeError):
                self.initializer().run()
        finally:
            os.environ["PATH"] = old
        assert not (self.home / ".gow-full-x86-state.json").exists()
        self.unchanged_external()

    def test_pipeline_failure_cannot_publish_marker(self) -> None:
        """Pipeline failure cannot publish marker."""
        bindir = self.base / "bin"
        bindir.mkdir()
        executable(bindir / "find", "#!/bin/sh\nexit 29\n")
        old = os.environ["PATH"]
        os.environ["PATH"] = str(bindir) + ":" + old
        try:
            with pytest.raises(RuntimeError):
                self.initializer().run()
        finally:
            os.environ["PATH"] = old
        assert not (self.home / ".gow-full-x86-state.json").exists()
        self.unchanged_external()

    def test_unrelated_userdata_and_interrupted_initialization_refused(self) -> None:
        """Unrelated userdata and interrupted initialization refused."""
        extra = self.final / "unrelated"
        extra.write_text("do not overwrite", encoding="utf-8")
        with pytest.raises(RuntimeError):
            self.initializer().run()
        assert extra.read_text(encoding="utf-8") == "do not overwrite"
        extra.unlink()
        (self.home / ".gow-full-x86-init").mkdir()
        with pytest.raises(RuntimeError):
            self.initializer().run()
        self.unchanged_external()

    def test_writable_library_mount_refused(self) -> None:
        """Writable library mount refused."""
        command("mount", "-o", "remount,bind,rw", str(self.final / "bios"))
        with pytest.raises(RuntimeError):
            self.initializer().run()
        assert not (self.home / ".gow-full-x86-init").exists()

    def test_marker_identity_change_refused_without_reseeding(self) -> None:
        """Marker identity change refused without reseeding."""
        self.initializer().run()
        with pytest.raises(RuntimeError):
            runtime.StateInitializer(self.uid + 1, self.gid).run()
        self.unchanged_external()

    def test_seed_symlink_escape_is_refused_before_stock_population(self) -> None:
        """Seed symlink escape is refused before stock population."""
        seed = self.base / "share"
        (seed / "system").symlink_to("/etc")
        command(
            "tar",
            "--numeric-owner",
            "-cpf",
            str(self.base / "stock-share.tar"),
            "-C",
            str(seed),
            ".",
        )
        with pytest.raises(RuntimeError):
            self.initializer().run()
        assert not (self.home / ".gow-full-x86-state.json").exists()
        self.unchanged_external()

    def test_changed_marker_release_and_ownership_are_refused(self) -> None:
        """Changed marker release and ownership are refused."""
        self.initializer().run()
        marker = self.home / ".gow-full-x86-state.json"
        data = json.loads(marker.read_text(encoding="utf-8"))
        data["release"] = "other"
        marker.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(RuntimeError):
            self.initializer().run()
        data["release"] = "43.1"
        marker.write_text(json.dumps(data), encoding="utf-8")
        os.chown(self.final / "system", self.uid + 1, self.gid)
        with pytest.raises(RuntimeError):
            self.initializer().run()
        self.unchanged_external()


class TestProcesses:
    """Exercise subprocess lifecycle and owned-resource cleanup."""

    # The autouse prepare_processes fixture initializes these inside its cleanup scope.
    # Constructors must not allocate subprocess state or temporary paths at collection.
    processes: list[  # pyright: ignore[reportUninitializedInstanceVariable]
        subprocess.Popen[str]
    ]
    base: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    bin: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    child_runtime: Path  # pyright: ignore[reportUninitializedInstanceVariable]
    env: dict[str, str]  # pyright: ignore[reportUninitializedInstanceVariable]
    driver: Path  # pyright: ignore[reportUninitializedInstanceVariable]

    @pytest.fixture(autouse=True)
    def prepare_processes(self) -> Iterator[None]:
        """Allocate disposable scripts and reap each owned child on teardown."""
        if (
            not Path("/.dockerenv").exists()
            or os.environ.get("GOW_RUNTIME_FIXTURE") != "1"
        ):
            pytest.skip("requires the isolated process fixture container")
        self.processes = []
        with tempfile.TemporaryDirectory() as temporary:
            try:
                self.prepare_process_tree(Path(temporary))
                yield
            finally:
                self.close_processes()

    def prepare_process_tree(self, base: Path) -> None:
        """Create owned executables and environment before any child is started."""
        self.base = base
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.child_runtime = self.base / "runtime"
        self.child_runtime.mkdir(mode=0o700)
        self.env = dict(
            os.environ,
            PATH=str(self.bin) + ":" + os.environ["PATH"],
            FIXTURE=str(self.base),
            GOW_CHILD_RUNTIME=str(self.child_runtime),
            PULSE_SERVER="/run/session-pulse",
            PULSE_SINK="virtual_sink_fixture",
            PULSE_SOURCE="virtual_sink_fixture.monitor",
            XDG_RUNTIME_DIR="/run/wolf-parent",
            WAYLAND_DISPLAY="wayland-fixture",
        )
        Path("/userdata").mkdir(exist_ok=True)
        executable(self.bin / "batocera-settings-get", "#!/bin/sh\nprintf en_US\n")
        self.driver = self.base / "driver.py"
        self.driver.write_text(
            "import os,sys,time,subprocess\n"
            "from pathlib import Path\n"
            "from batocera_gow.runtime import runtime as r\n"
            "r.HERE=Path('/project/build-assets/runtime')\n"
            "try:\n"
            " if sys.argv[1]=='frontend':\n"
            "  result=r.Frontend(r.launch_process,time.monotonic,time.sleep)"
            ".run(dict(os.environ),Path(os.environ['FIXTURE']))\n"
            " else:\n"
            "  r.nvidia_environments=lambda e,p:(dict(e),dict(e))\n"
            "  r.require_alsa_pulse=lambda:None\n"
            "  result=r.Session(r.launch_process,time.monotonic,time.sleep)"
            ".run([os.environ['FRONTEND']],dict(os.environ))\n"
            "except InterruptedError: result=143\n"
            "except Exception as e: print(e,file=sys.stderr);result=1\n"
            "sys.exit(result)\n",
            encoding="utf-8",
        )

    def close_processes(self) -> None:
        """Stop only tracked fixture processes and release their temporary tree."""
        for child in self.processes:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            if child.stderr:
                child.stderr.close()

    def start(
        self,
        action: str,
        *,
        user: int | None = None,
        group: int | None = None,
        extra_groups: list[int] | None = None,
        pass_fds: tuple[int, ...] = (),
    ) -> subprocess.Popen[str]:
        """Start a fixture driver with explicitly selected child privileges."""
        # Driver and argv belong exclusively to the disposable process fixture.
        child = subprocess.Popen(  # noqa: S603
            [sys.executable, str(self.driver), action],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            user=user,
            group=group,
            extra_groups=extra_groups,
            pass_fds=pass_fds,
        )
        self.processes.append(child)
        return child

    def es(self, body: str) -> str:
        """Install a frontend fixture that records every invocation."""
        return executable(
            self.bin / "emulationstation",
            "#!/usr/bin/python3\nimport os,sys,time,json,signal\n"
            "from pathlib import Path\np=Path(os.environ['FIXTURE'])\n"
            "with (p/'launches').open('a') as f:"
            "f.write(json.dumps(sys.argv)+'\\n')\n" + body,
        )

    def test_plain_exit_does_not_restart(self) -> None:
        """Plain exit does not restart."""
        self.es("sys.exit(7)\n")
        child = self.start("frontend")
        assert child.wait(timeout=5) == 7
        assert (
            len((self.base / "launches").read_text(encoding="utf-8").splitlines()) == 1
        )

    def test_restart_consumes_flag_and_disables_startup_game(self) -> None:
        """Restart consumes flag and disables startup game."""
        self.es(
            "if len((p/'launches').read_text().splitlines())==1:"
            "(p/'restart.please').touch()\n"
        )
        child = self.start("frontend")
        assert child.wait(timeout=5) == 0
        launches = [
            json.loads(line)
            for line in (self.base / "launches")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert len(launches) == 2
        assert "--no-startup-game" in launches[1]
        assert not (self.base / "restart.please").exists()

    def test_shutdown_and_reboot_end_session(self) -> None:
        """Shutdown and reboot end session."""
        for flag in ("shutdown.please", "reboot.please"):
            (self.base / "launches").unlink(missing_ok=True)
            self.es(f"(p/{flag!r}).touch()\n")
            child = self.start("frontend")
            assert child.wait(timeout=5) == 0
            assert (
                len((self.base / "launches").read_text(encoding="utf-8").splitlines())
                == 1
            )
            assert not (self.base / flag).exists()

    def test_suspend_term_is_interruptible(self) -> None:
        """Suspend term is interruptible."""
        self.es("(p/'suspend.please').touch()\n")
        child = self.start("frontend")
        wait_for((self.base / "es-resume.fifo").exists)
        child.terminate()
        assert child.wait(timeout=5) == 143
        assert not (self.base / "es-resume.fifo").exists()

    def test_suspend_resume_restarts_frontend(self) -> None:
        """Suspend resume restarts frontend."""
        self.es(
            "if len((p/'launches').read_text().splitlines())==1:"
            "(p/'suspend.please').touch()\n"
        )
        child = self.start("frontend")
        wait_for((self.base / "es-resume.fifo").exists)
        with (self.base / "es-resume.fifo").open("w", encoding="utf-8") as stream:
            stream.write("resume\n")
        assert child.wait(timeout=5) == 0
        assert (
            len((self.base / "launches").read_text(encoding="utf-8").splitlines()) == 2
        )

    def session_tools(
        self,
        *,
        bridge_body: str = "time.sleep(60)",
        ready: bool = True,
        frontend_body: str = "time.sleep(0.2)",
    ) -> None:
        """Install subprocess fixtures without contacting a compositor or Wolf."""
        # These are lifecycle fixtures, not a compositor or a local Wolf server.
        # The readiness peer reads the actual private cookie and the bridge must
        # publish that same token before authentication can succeed.
        prefix = (
            "#!/usr/bin/python3\nimport os,sys,time,json\n"
            "from pathlib import Path\np=Path(os.environ['FIXTURE'])\n"
        )
        self.env["GOW_XAUTH"] = executable(
            self.bin / "xauth", prefix + "Path(sys.argv[2]).write_text(sys.argv[-1])\n"
        )
        self.env["GOW_XWAYLAND"] = executable(
            self.bin / "Xwayland",
            prefix + "(p/'bridge.pid').write_text(str(os.getpid()))\n"
            "(p/'bridge-cookie').write_text("
            "Path(sys.argv[sys.argv.index('-auth')+1]).read_text())\n"
            + bridge_body
            + "\n",
        )
        readiness = (
            "sys.exit(0 if (p/'bridge-cookie').exists() and "
            "(p/'bridge-cookie').read_text()=="
            "Path(os.environ['XAUTHORITY']).read_text() else 1)"
            if ready
            else "sys.exit(1)"
        )
        executable(self.bin / "xset", prefix + readiness + "\n")
        executable(self.bin / "batocera-resolution", prefix)
        executable(
            self.bin / "openbox",
            prefix + "(p/'openbox.pid').write_text(str(os.getpid()))\ntime.sleep(60)\n",
        )
        (self.base / "mapped-input").write_text("forwarded input", encoding="utf-8")
        executable(
            self.bin / "hotkeygen",
            prefix + "import signal,types\n"
            "class Daemon:\n"
            " def __init__(self,permanent):self.permanent=permanent\n"
            " def _Daemon__handle_actions(self,action,device):\n"
            "  Path(device.device_node).read_bytes()\n"
            "  if os.environ.get('HOTKEY_FIXTURE_CONFIG'):"
            "Path(os.environ['HOTKEY_FIXTURE_CONFIG']).read_text()\n"
            " def run(self):\n"
            "  for name in ('unmounted-input','mapped-input'):\n"
            "   self._Daemon__handle_actions('add',"
            "types.SimpleNamespace(device_node=str(p/name)))\n"
            "  (p/'hotkeygen.pid').write_text(str(os.getpid()))\n"
            "  time.sleep(0.15)\n"
            "  signal.signal(signal.SIGHUP,lambda *_:None)\n  time.sleep(60)\n"
            "if __name__=='__main__':\n"
            " if '--default-context' in sys.argv:"
            "os.kill(int((p/'hotkeygen.pid').read_text()),signal.SIGHUP)\n"
            " else:Daemon(permanent=True).run()\n",
        )
        self.env["FRONTEND"] = executable(
            self.bin / "frontend",
            prefix + "(p/'frontend.pid').write_text(str(os.getpid()))\n"
            "(p/'frontend-env').write_text(json.dumps(dict(os.environ)))\n"
            + frontend_body
            + "\n",
        )

    def assert_owned_dead(self) -> None:
        """Require every recorded fixture-owned process to have been reaped."""
        for path in self.base.glob("*.pid"):
            pid = int(path.read_text(encoding="utf-8"))
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    def test_session_authenticated_readiness_and_cleanup(self) -> None:
        """Session authenticated readiness and cleanup."""
        self.session_tools()
        unrelated = subprocess.Popen(["/usr/bin/sleep", "60"], text=True)
        self.processes.append(unrelated)
        child = self.start("session")
        assert child.stderr is not None
        assert child.wait(timeout=8) == 0, child.stderr.read()
        assert unrelated.poll() is None
        self.assert_owned_dead()
        env = json.loads((self.base / "frontend-env").read_text(encoding="utf-8"))
        assert env["XDG_RUNTIME_DIR"] == str(self.child_runtime)
        assert env["PULSE_SERVER"] == "unix:/run/session-pulse"
        assert env["DISPLAY"] == ":0"
        assert "WAYLAND_DISPLAY" not in env
        assert not (self.child_runtime / "Xauthority").exists()

    def test_root_owned_wayland_connection_survives_privilege_drop_for_bridge_only(
        self,
    ) -> None:
        """Root owned wayland connection survives privilege drop for bridge only."""
        self.session_tools(
            bridge_body=(
                "os.write(int(os.environ['WAYLAND_SOCKET']), b'bridge-connected');"
                "time.sleep(60)"
            )
        )
        uid, gid = 1234, 1235
        runtime.account(uid, gid)
        os.chown(self.base, uid, gid)
        os.chown(self.child_runtime, uid, gid)
        path = self.base / "wayland-root"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            path.chmod(0o700)
            listener.listen(1)
            listener.settimeout(5)
            before = path.stat()
            # The child only checks access to this fixture-owned Unix socket.
            denied = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-c",
                    (
                        "import socket,sys\ns=socket.socket(socket.AF_UNIX)\n"
                        "try:s.connect(sys.argv[1])\n"
                        "except PermissionError:sys.exit(0)\n"
                        "sys.exit(1)\n"
                    ),
                    str(path),
                ],
                user=uid,
                group=gid,
                extra_groups=[],
                check=False,
            )
            assert denied.returncode == 0
            with runtime.connect_wayland(
                {"XDG_RUNTIME_DIR": str(self.base), "WAYLAND_DISPLAY": path.name}
            ) as connection:
                self.env["WAYLAND_SOCKET"] = str(connection.fileno())
                child = self.start(
                    "session",
                    user=uid,
                    group=gid,
                    extra_groups=[],
                    pass_fds=(connection.fileno(),),
                )
                with listener.accept()[0] as peer:
                    peer.settimeout(5)
                    assert peer.recv(64) == b"bridge-connected"
                assert child.stderr is not None
                assert child.wait(timeout=8) == 0, child.stderr.read()
            after = path.stat()
            assert (after.st_uid, after.st_gid, after.st_mode) == (
                before.st_uid,
                before.st_gid,
                before.st_mode,
            )
        frontend_env = json.loads(
            (self.base / "frontend-env").read_text(encoding="utf-8")
        )
        assert "WAYLAND_SOCKET" not in frontend_env
        self.assert_owned_dead()

    def test_missing_hotkey_config_is_not_ignored_as_unmounted_input(self) -> None:
        """Missing hotkey config is not ignored as unmounted input."""
        self.session_tools()
        self.env["HOTKEY_FIXTURE_CONFIG"] = str(self.base / "missing-context")
        child = self.start("session")
        assert child.wait(timeout=8) != 0
        assert child.stderr is not None
        assert "missing-context" in child.stderr.read()
        assert not (self.base / "frontend.pid").exists()
        self.assert_owned_dead()

    def test_bridge_death_ends_session_without_frontend_restart(self) -> None:
        """Bridge death ends session without frontend restart."""
        self.session_tools(
            bridge_body="time.sleep(0.8)", frontend_body="time.sleep(60)"
        )
        child = self.start("session")
        assert child.wait(timeout=8) != 0
        self.assert_owned_dead()

    def test_readiness_timeout_never_launches_frontend(self) -> None:
        """Readiness timeout never launches frontend."""
        self.session_tools(ready=False)
        child = self.start("session")
        assert child.wait(timeout=15) != 0
        assert not (self.base / "frontend.pid").exists()
        self.assert_owned_dead()

    def test_term_cleans_owned_session_processes(self) -> None:
        """Term cleans owned session processes."""
        self.session_tools(frontend_body="time.sleep(60)")
        child = self.start("session")
        wait_for((self.base / "frontend.pid").exists)
        child.terminate()
        assert child.wait(timeout=8) == 143
        self.assert_owned_dead()

    def test_term_reaps_nested_frontend_group_even_when_es_ignores_term(self) -> None:
        """Term reaps nested frontend group even when es ignores term."""
        self.session_tools()
        self.es(
            "(p/'es.pid').write_text(str(os.getpid()))\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\ntime.sleep(60)\n"
        )
        self.env["FRONTEND"] = executable(
            self.bin / "frontend",
            "#!/bin/sh\n"
            f"exec {shlex.quote(sys.executable)} "
            '"$FIXTURE/driver.py" frontend\n',
        )
        child = self.start("session")
        wait_for((self.base / "es.pid").exists)
        child.terminate()
        assert child.wait(timeout=8) == 143
        self.assert_owned_dead()
