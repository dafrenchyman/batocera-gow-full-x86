"""Stock Batocera state and single-container Wolf session adapter."""

import argparse
import filecmp
import grp
import json
import os
import pwd
import re
import runpy
import secrets
import selectors
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from types import FrameType, new_class
from typing import Never, Protocol, TextIO, runtime_checkable

from .duckstation_install import install_override
from .resources import RUNTIME_ROOT

HERE = RUNTIME_ROOT
RELEASE = "43.1"
HOME = Path("/home/retro")
MAX_ID = 4_294_967_294


def fail(message: str) -> Never:
    """Refuse an unsafe runtime operation with a caller-facing explanation."""
    raise RuntimeError(message)


def _executable(name: str) -> str:
    """Resolve a stock command through the existing runtime PATH selection."""
    path = shutil.which(name)
    if path is None:
        fail("missing runtime executable: " + name)
    return path


def numeric(value: str, name: str, *, positive: bool = False) -> int:
    """Parse an unsigned identity or positive session dimension.

    Values above the Linux usable UID/GID range are rejected.
    """
    if (
        not re.fullmatch(r"[0-9]+", value)
        or int(value) > MAX_ID
        or (positive and int(value) == 0)
    ):
        fail("invalid " + name)
    return int(value)


def identity(env: Mapping[str, str]) -> tuple[int, int]:
    """Resolve application UID/GID, preserving an explicitly configured zero."""
    return numeric(env.get("PUID", "1000"), "PUID"), numeric(
        env.get("PGID", "1000"), "PGID"
    )


def _session_resolution(env: Mapping[str, str]) -> str:
    width = numeric(
        env.get("GAMESCOPE_WIDTH", "1920"), "GAMESCOPE_WIDTH", positive=True
    )
    height = numeric(
        env.get("GAMESCOPE_HEIGHT", "1080"), "GAMESCOPE_HEIGHT", positive=True
    )
    return f"{width}x{height}"


def real_directory(path: Path) -> None:
    """Require a real directory, never a symlink at the supplied path."""
    if path.is_symlink() or not path.is_dir():
        fail("expected real directory: " + str(path))


def safe_link(path: Path, target: Path, allowed: Sequence[Path] = ()) -> None:
    """Replace only an empty directory or recognized link with the target."""
    if path.is_symlink():
        # Path.readlink normalizes text; link recognition must compare exact bytes.
        if os.readlink(path) not in (str(target), *map(str, allowed)):  # noqa: PTH115
            fail("unrecognized symlink: " + str(path))
        path.unlink()
    elif path.exists():
        if not path.is_dir() or any(path.iterdir()):
            fail("conflicting path: " + str(path))
        path.rmdir()
    path.symlink_to(target)


def chown_tree(path: Path, uid: int, gid: int) -> None:
    """Set ownership recursively without following any symlink."""
    os.chown(path, uid, gid, follow_symlinks=False)
    if path.is_symlink():
        return
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            os.chown(Path(directory) / name, uid, gid, follow_symlinks=False)


class StateInitializer:
    """Populate owned userdata once while retaining interrupted-state refusals."""

    def __init__(self, uid: int, gid: int, home: Path = HOME) -> None:
        """Configure the mounted home and identities without changing state."""
        self.uid, self.gid, self.home = uid, gid, home
        self.final = home / "userdata"
        self.work = home / ".gow-full-x86-init"
        self.stage = self.work / "userdata"
        self.seed = home / ".gow-full-x86-stock-seed"
        self.marker = home / ".gow-full-x86-state.json"

    def validate_outputs(self) -> None:
        """Require the populated release and nonempty stock identity outputs."""
        for relative in (
            "system/data.version",
            "system/batocera.conf",
            "system/machine-id",
        ):
            path = self.final / relative
            if not path.resolve().is_relative_to(self.final):
                fail("initialized path escapes userdata: " + str(path))
            if not path.is_file() or path.is_symlink() or not path.stat().st_size:
                fail("missing initialized output: " + str(path))
        if (self.final / "system/data.version").read_text(
            encoding="utf-8"
        ).strip() != Path("/usr/share/batocera/batocera.version").read_text(
            encoding="utf-8"
        ).strip():
            fail("initialized data.version differs from packaged release")

    def links(self) -> None:
        """Expose userdata and stock machine identity through recognized links."""
        safe_link(Path("/userdata"), self.final)
        for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
            if path.is_symlink():
                # Preserve exact stock target spelling, not Path normalization.
                if os.readlink(path) != "/userdata/system/machine-id":  # noqa: PTH115
                    fail("unrecognized machine-id link: " + str(path))
                path.unlink()
            elif path.exists():
                if not path.is_file():
                    fail("invalid machine-id destination")
                path.unlink()
            path.symlink_to("/userdata/system/machine-id")

    # Keep the no-follow descriptor walk and publication checks in one audited
    # transaction so descriptor ownership remains visible through publication.
    def prepare_generated_controller_db(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """Expose one absent stock output backed by owned userdata.

        Root operations use no-follow directory descriptors, never a checked
        pathname whose ancestors the app can replace. Existing files and
        unexpected links are refused. The caller still owns the userdata lease;
        descriptor traversal does not reserve names against concurrent renames.
        """
        destination = Path("/usr/share/duckstation/resources/gamecontrollerdb.txt")
        target = (
            self.final
            / "system/.gow-full-x86-generated/duckstation/gamecontrollerdb.txt"
        )
        if (
            not self.home.is_absolute()
            or self.home == Path("/")
            or ".." in self.home.parts
        ):
            fail("unsafe generated controller database home")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            with ExitStack() as descriptors:
                root = os.open("/", flags)
                descriptors.callback(os.close, root)
                directories: list[tuple[int, str, int]] = []

                def open_directory(parent: int, name: str) -> int:
                    descriptor = os.open(name, flags, dir_fd=parent)
                    descriptors.callback(os.close, descriptor)
                    directories.append((parent, name, descriptor))
                    return descriptor

                stock = root
                for name in (None, "usr", "share", "duckstation", "resources"):
                    if name is not None:
                        stock = open_directory(stock, name)
                    info = os.fstat(stock)
                    if (info.st_uid, info.st_gid) != (0, 0) or info.st_mode & 0o022:
                        fail("unsafe stock controller database directory")
                try:
                    link = os.stat(
                        destination.name, dir_fd=stock, follow_symlinks=False
                    )
                except FileNotFoundError:
                    link = None
                if link is not None and (
                    not stat.S_ISLNK(link.st_mode)
                    or (link.st_uid, link.st_gid) != (0, 0)
                    or os.readlink(destination.name, dir_fd=stock) != str(target)
                ):
                    fail("unexpected stock controller database destination")

                data = root
                for name in self.home.parts[1:-1]:
                    data = open_directory(data, name)
                    info = os.fstat(data)
                    if (info.st_uid, info.st_gid) != (0, 0) or info.st_mode & 0o022:
                        fail("unsafe generated controller database ancestor")
                for name, create in (
                    (self.home.name, False),
                    ("userdata", False),
                    ("system", False),
                    (".gow-full-x86-generated", True),
                    ("duckstation", True),
                ):
                    created = False
                    parent_info = os.fstat(data)
                    created_gid = (
                        parent_info.st_gid
                        if parent_info.st_mode & stat.S_ISGID
                        else os.getegid()
                    )
                    if create:
                        try:
                            os.mkdir(name, mode=0o700, dir_fd=data)
                        except FileExistsError:
                            pass
                        else:
                            created = True
                    data = open_directory(data, name)
                    info = os.fstat(data)
                    expected_owner = (
                        (0, created_gid) if created else (self.uid, self.gid)
                    )
                    if (info.st_uid, info.st_gid) != expected_owner:
                        fail("unsafe generated controller database directory")
                    if created:
                        os.fchown(data, self.uid, self.gid)
                        info = os.fstat(data)
                        if (info.st_uid, info.st_gid) != (self.uid, self.gid):
                            fail(
                                "generated controller database directory owner changed"
                            )

                created = False
                try:
                    descriptor = os.open(
                        target.name,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_NOFOLLOW
                        | os.O_CLOEXEC,
                        0o600,
                        dir_fd=data,
                    )
                except FileExistsError:
                    # O_PATH inspects even a FIFO or device without opening it
                    # for I/O, and O_NOFOLLOW leaves a symlink itself inspectable.
                    descriptor = os.open(
                        target.name,
                        os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=data,
                    )
                else:
                    created = True
                descriptors.callback(os.close, descriptor)
                info = os.fstat(descriptor)
                parent_info = os.fstat(data)
                created_gid = (
                    parent_info.st_gid
                    if parent_info.st_mode & stat.S_ISGID
                    else os.getegid()
                )
                expected_owner = (0, created_gid) if created else (self.uid, self.gid)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or (info.st_uid, info.st_gid) != expected_owner
                ):
                    fail("unsafe generated controller database file")
                if created:
                    os.fchown(descriptor, self.uid, self.gid)
                info = os.fstat(descriptor)
                if info.st_nlink != 1 or (info.st_uid, info.st_gid) != (
                    self.uid,
                    self.gid,
                ):
                    fail("generated controller database file owner or links changed")
                current = os.stat(target.name, dir_fd=data, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    fail("generated controller database file was replaced")
                # Refuse observed substitutions before publishing the fixed
                # link. This check is not an atomic concurrent-rename barrier.
                for parent, name, descriptor in directories:
                    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    opened = os.fstat(descriptor)
                    if (current.st_dev, current.st_ino) != (
                        opened.st_dev,
                        opened.st_ino,
                    ):
                        fail("generated controller database ancestor was replaced")
                if link is None:
                    os.symlink(str(target), destination.name, dir_fd=stock)
        except OSError as error:
            message = "cannot safely prepare generated controller database"
            raise RuntimeError(message) from error

    def install_duckstation_override(self) -> None:
        """Install only the absent project PSX override before ES reads it."""
        disposition = install_override(
            self.home, self.uid, self.gid, HERE / "es_systems_gow_duckstation.cfg"
        )
        sys.stderr.write("DuckStation PSX override: " + disposition + "\n")

    def populate(self) -> None:
        """Run stock SHARE population and check newly seeded ROM tree bytes."""
        # The stock script tolerates absent optional defaults, including ES's
        # first-run settings file. Do not impose errexit on its control flow.
        # Still verify the ROM trees it must copy into previously absent roots.
        sources = []
        for source in Path("/usr/share/batocera/datainit/roms").iterdir():
            destination = self.stage / "roms" / source.name
            if (
                source.is_dir()
                and not source.is_symlink()
                and not destination.exists()
                and not destination.is_symlink()
            ):
                sources.append((source, destination))
        # Execute the unchanged stock population script using the selected PATH.
        subprocess.run(  # noqa: S603
            [_executable("bash"), "/etc/init.d/S12populateshare", "start"], check=True
        )
        for source, destination in sources:
            real_directory(destination)
            for directory, dirs, files in os.walk(source, followlinks=False):
                for name in dirs + files:
                    original = Path(directory) / name
                    copied = destination / original.relative_to(source)
                    if original.is_symlink():
                        # Stock seed links must retain their exact target text.
                        if not copied.is_symlink() or os.readlink(  # noqa: PTH115
                            copied
                        ) != os.readlink(original):  # noqa: PTH115
                            fail(
                                "stock ROM seed link missing or changed: " + str(copied)
                            )
                    elif original.is_dir():
                        real_directory(copied)
                    elif (
                        copied.is_symlink()
                        or not copied.is_file()
                        or not filecmp.cmp(original, copied, shallow=False)
                    ):
                        fail("stock ROM seed file missing or changed: " + str(copied))

    def run(self) -> None:
        """Initialize or validate state, publishing the marker only on success.

        Failed population deliberately leaves its interrupted-state evidence.
        It must not be retried over a partially installed tree.
        """
        real_directory(self.home)
        if self.home.resolve() != self.home:
            fail("home has a symlinked ancestor")
        if not self.final.exists():
            self.final.mkdir()
        real_directory(self.final)
        Path("/var/lib/dbus").mkdir(parents=True, exist_ok=True)
        expected: dict[str, str | int] = {
            "release": RELEASE,
            "puid": self.uid,
            "pgid": self.gid,
        }
        if self.marker.exists() or self.marker.is_symlink():
            self._validate_marker(expected)
            self.validate_outputs()
            self.links()
            self.prepare_generated_controller_db()
            self.install_duckstation_override()
            return
        self._require_uninitialized()
        self._seed_new()
        self._install_populated_tree()
        self.validate_outputs()
        self.links()
        self.prepare_generated_controller_db()
        self.install_duckstation_override()
        self._publish_marker(expected)

    def _validate_marker(self, expected: Mapping[str, str | int]) -> None:
        """Refuse another release, account identity or unexpected state owner."""
        if (
            self.marker.is_symlink()
            or json.loads(self.marker.read_text(encoding="utf-8")) != expected
        ):
            fail("state release/identity mismatch")
        for path in (self.home, self.final, self.final / "system", self.marker):
            info = path.stat()
            if info.st_uid != self.uid or info.st_gid != self.gid:
                fail("state ownership mismatch: " + str(path))

    def _require_uninitialized(self) -> None:
        """Refuse interrupted initialization and unrelated userdata content."""
        if (
            self.work.exists()
            or self.work.is_symlink()
            or self.seed.exists()
            or self.seed.is_symlink()
        ):
            fail("interrupted or unrelated initialization directory")
        if {p.name for p in self.final.iterdir()} - {"roms", "bios"}:
            fail("unrecognized contents in uninitialized userdata")
        if (
            Path("/boot/postshare.sh").exists()
            or Path("/boot/postshare.sh").is_symlink()
        ):
            fail("unexpected /boot/postshare.sh")

    def _seed_new(self) -> None:
        """Extract and populate the complete stock seed away from library binds."""
        self.work.mkdir(mode=0o700)
        self.stage.mkdir()
        # Only the immutable staged SHARE archive and owned staging path are argv.
        subprocess.run(  # noqa: S603
            [
                _executable("tar"),
                "--numeric-owner",
                "--acls",
                "--xattrs",
                "--xattrs-include=*",
                "-xpf",
                str(HERE / "stock-share.tar"),
                "-C",
                str(self.stage),
            ],
            check=True,
        )
        for directory, dirs, files in os.walk(self.stage, followlinks=False):
            for name in dirs + files:
                path = Path(directory) / name
                if path.is_symlink() and not path.resolve().is_relative_to(self.stage):
                    fail("SHARE seed symlink escapes staging: " + str(path))
        system = self.stage / "system"
        system.mkdir(exist_ok=True)
        real_directory(system)
        version = system / "data.version"
        if version.is_symlink():
            fail("seed data.version is a symlink")
        if not version.exists():
            version.touch()
        safe_link(Path("/userdata"), self.stage, allowed=(self.final,))
        self.populate()

    def _install_populated_tree(self) -> None:
        """Install absent roots without writing into existing operator libraries."""
        for child in self.stage.iterdir():
            destination = self.final / child.name
            if child.name in ("roms", "bios") and (
                destination.exists() or destination.is_symlink()
            ):
                continue
            if destination.exists() or destination.is_symlink():
                fail("userdata collision: " + str(destination))
            child.rename(destination)
            chown_tree(destination, self.uid, self.gid)
        self.stage.rename(self.seed)
        self.work.rmdir()
        chown_tree(self.seed, self.uid, self.gid)
        os.chown(self.final, self.uid, self.gid)
        os.chown(self.home, self.uid, self.gid)
        safe_link(Path("/userdata"), self.final, allowed=(self.stage,))

    def _publish_marker(self, expected: Mapping[str, str | int]) -> None:
        """Publish successful population last, after every stock output check."""
        # Atomic marker publication is the final operation. Failed initialization
        # is deliberately not retried over a partially installed tree.
        temporary = self.home / ".gow-full-x86-state.json.partial"
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(expected, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, self.uid, self.gid)
        temporary.replace(self.marker)


def normalize_audio(env: dict[str, str]) -> dict[str, str]:
    """Route both SDL versions through ALSA to the required Wolf Pulse session.

    The supplied environment is updated in place and returned.
    """
    server = env.get("PULSE_SERVER")
    if not server or not env.get("PULSE_SINK") or not env.get("PULSE_SOURCE"):
        fail("Wolf session Pulse server, sink and source are required")
    if server.startswith("/"):
        env["PULSE_SERVER"] = "unix:" + server
    # Stock SDL2 lacks a Pulse backend; route both SDL versions through the
    # session's ALSA Pulse plugin rather than the appliance's PipeWire server.
    for variable in ("SDL_AUDIODRIVER", "SDL_AUDIO_DRIVER"):
        env[variable] = "alsa"
    env["ALSA_CONFIG_PATH"] = str(HERE / "alsa.conf")
    return env


def require_alsa_pulse() -> None:
    """Refuse startup unless both stock ALSA Pulse plugins are present."""
    for module in ("pcm", "ctl"):
        if not any(
            Path("/usr").glob(f"lib*/alsa-lib/libasound_module_{module}_pulse.so")
        ) and not any(
            Path("/usr/lib").glob(f"*/alsa-lib/libasound_module_{module}_pulse.so")
        ):
            fail("stock ALSA Pulse " + module + " module is missing")


def _driver_manifest(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Decode vendor JSON while retaining fields unrelated to the library path."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        fail("invalid NVIDIA driver manifest: " + str(path))
    document: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            fail("invalid NVIDIA driver manifest key")
        document[key] = value
    raw_icd = document.get("ICD")
    if not isinstance(raw_icd, dict):
        fail("missing NVIDIA driver manifest ICD")
    icd: dict[str, object] = {}
    for key, value in raw_icd.items():
        if not isinstance(key, str):
            fail("invalid NVIDIA driver manifest ICD key")
        icd[key] = value
    if not isinstance(icd.get("library_path"), str):
        fail("missing NVIDIA driver manifest library_path")
    document["ICD"] = icd
    return document, icd


def nvidia_environments(
    env: Mapping[str, str], runtime: Path
) -> tuple[dict[str, str], dict[str, str]]:
    """Write private vendor selectors and separate bridge/application loaders.

    Injected NVIDIA files and stock loader symlinks remain unchanged. The caller
    owns the private runtime directory and removes it after failed startup.
    """
    payload = Path("/usr/nvidia")
    glx = sorted(p for p in payload.glob("lib/libGLX_nvidia.so*") if p.is_file())
    egl = sorted(p for p in payload.glob("lib/libEGL_nvidia.so*") if p.is_file())
    if not glx or not egl or not Path("/dev/nvidiactl").exists():
        fail("NVIDIA device or injected /usr/nvidia/lib GLX/EGL payload is missing")
    driver_dirs = [str(payload / "lib"), str(payload / "lib32")]
    # Preserve the injected ICD API version and point each vendor loader at the
    # injected implementation, not the appliance's potentially older driver.
    egl_data, egl_icd = _driver_manifest(
        payload / "share/glvnd/egl_vendor.d/10_nvidia.json"
    )
    vk_data, vk_icd = _driver_manifest(payload / "share/vulkan/icd.d/nvidia_icd.json")
    egl_icd["library_path"] = str(egl[0])
    vk_icd["library_path"] = str(glx[0])
    egl_json = runtime / "nvidia-egl.json"
    egl_json.write_text(json.dumps(egl_data), encoding="utf-8")
    vk_json = runtime / "nvidia-vulkan.json"
    vk_json.write_text(json.dumps(vk_data), encoding="utf-8")
    common = {
        "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
        "__EGL_VENDOR_LIBRARY_FILENAMES": str(egl_json),
        "VK_ICD_FILENAMES": str(vk_json),
        "VK_DRIVER_FILES": str(vk_json),
        "GBM_BACKEND": "nvidia-drm",
        "GBM_BACKENDS_PATH": str(payload / "lib/gbm"),
    }
    external = []
    for source in sorted(
        (payload / "share/egl/egl_external_platform.d").glob("*.json")
    ):
        data, icd = _driver_manifest(source)
        library_path = icd["library_path"]
        if not isinstance(library_path, str):
            fail("invalid NVIDIA EGL platform library path")
        library = payload / "lib" / Path(library_path).name
        if not library.is_file():
            fail("missing injected NVIDIA EGL platform library: " + str(library))
        icd["library_path"] = str(library)
        destination = runtime / source.name
        destination.write_text(json.dumps(data), encoding="utf-8")
        external.append(str(destination))
    if external:
        common["__EGL_EXTERNAL_PLATFORM_CONFIG_FILENAMES"] = ":".join(external)
    app = dict(env, **common)
    app["LD_LIBRARY_PATH"] = ":".join(
        driver_dirs + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    # Wine and stock configgen replace LD_LIBRARY_PATH. Preload the injected
    # CUDA and GLX sonames before their later bare-name dlopen calls.
    cuda = runtime / "injected-cuda"
    for token, directory in (("lib64", "lib"), ("lib", "lib32")):
        destination = cuda / token
        destination.mkdir(mode=0o700, parents=True)
        for name, label in (("libcuda.so.1", "CUDA"), ("libGLX_nvidia.so.0", "GLX")):
            library = payload / directory / name
            if not library.is_file():
                fail(f"missing injected NVIDIA {label} library: {library}")
            (destination / name).symlink_to(library)
    preload = ":".join(
        str(cuda / "$LIB" / name) for name in ("libcuda.so.1", "libGLX_nvidia.so.0")
    )
    app["LD_PRELOAD"] = preload + (
        ":" + env["LD_PRELOAD"] if env.get("LD_PRELOAD") else ""
    )
    bridge = dict(env, **common)
    bridge["LD_LIBRARY_PATH"] = ":".join(
        driver_dirs
        + (
            [env["GOW_BRIDGE_LIBRARY_PATH"]]
            if env.get("GOW_BRIDGE_LIBRARY_PATH")
            else []
        )
    )
    if env.get("GOW_MESA_DRIVERS"):
        bridge["LIBGL_DRIVERS_PATH"] = env["GOW_MESA_DRIVERS"]
    return bridge, app


class ProcessFactory(Protocol):
    """Create a new owned binary-mode process group without owning its streams."""

    def __call__(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None,
        stdout: TextIO | int | None,
        stderr: int | None,
        pass_fds: Sequence[int],
    ) -> subprocess.Popen[bytes]:
        """Start the supplied argv with explicit descriptor inheritance."""
        ...


def launch_process(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None,
    stdout: TextIO | int | None,
    stderr: int | None,
    pass_fds: Sequence[int],
) -> subprocess.Popen[bytes]:
    """Launch approved runtime argv in its own group, borrowing passed streams."""
    return subprocess.Popen(  # noqa: S603  # Runtime command selection is explicit.
        command,
        env=env,
        start_new_session=True,
        stdout=stdout,
        stderr=stderr,
        pass_fds=pass_fds,
    )


class ProcessSupervisor:
    """Own only processes it starts and borrow its factory, clock and sleeper."""

    def __init__(
        self,
        process_factory: ProcessFactory,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        """Configure process creation and timing without allocating resources."""
        self.children: list[subprocess.Popen[bytes]] = []
        self.stopping = False
        self.signal_number: int | None = None
        self._process_factory = process_factory
        self._monotonic = monotonic
        self._sleep = sleep
        self._handlers: dict[
            signal.Signals, Callable[[int, FrameType | None], object] | int | None
        ] = {}

    def signal(self, number: int, frame: FrameType | None) -> None:
        """Record a termination request for the normal owned-child cleanup."""
        del frame
        self.stopping = True
        self.signal_number = number

    def install_signals(self) -> None:
        """Temporarily handle TERM/INT, retaining the caller's handlers."""
        for number in (signal.SIGTERM, signal.SIGINT):
            if number not in self._handlers:
                self._handlers[number] = signal.getsignal(number)
            signal.signal(number, self.signal)

    def spawn(
        self,
        command: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        stdout: TextIO | int | None = None,
        stderr: int | None = None,
        pass_fds: Sequence[int] = (),
    ) -> subprocess.Popen[bytes]:
        """Start and own one process group; supplied file objects stay borrowed."""
        child = self._process_factory(
            command,
            env=env,
            stdout=stdout,
            stderr=stderr,
            pass_fds=pass_fds,
        )
        self.children.append(child)
        return child

    def check(self, children: Sequence[subprocess.Popen[bytes]]) -> None:
        """Refuse cancellation or an exited required session dependency."""
        if self.stopping:
            raise InterruptedError(128 + (self.signal_number or signal.SIGTERM))
        for child in children:
            if child.poll() is not None:
                fail("required process exited: " + str(child.args))

    def close(self, grace: float = 3) -> None:
        """Stop every owned group, reap it and restore borrowed signal handlers.

        Cleanup continues across individual process failures. Only container PID
        one reaps adopted descendants; ordinary callers retain unrelated children.
        """
        errors: list[Exception] = []
        try:
            self._signal_groups(self.signal_number or signal.SIGTERM, errors)
            deadline = self._monotonic() + grace
            while self._monotonic() < deadline:
                if all(child.poll() is not None for child in self.children):
                    break
                self._sleep(0.05)
            self._signal_groups(signal.SIGKILL, errors)
            self._wait_owned(errors)
            self._reap_adopted()
        finally:
            for number, handler in self._handlers.items():
                signal.signal(number, handler)
            self._handlers.clear()
        if errors:
            message = "owned process cleanup failed"
            raise ExceptionGroup(message, errors)

    def _signal_groups(self, number: int, errors: list[Exception]) -> None:
        """Attempt every owned group even if one signal operation fails."""
        for child in self.children:
            try:
                os.killpg(child.pid, number)
            except ProcessLookupError:
                pass
            except OSError as error:
                errors.append(error)

    def _wait_owned(self, errors: list[Exception]) -> None:
        """Reap owned leaders without abandoning siblings after a wait failure."""
        for child in self.children:
            try:
                child.wait()
            except (OSError, subprocess.SubprocessError) as error:
                errors.append(error)
        self.children.clear()

    @staticmethod
    def _reap_adopted() -> None:
        """Reap adopted descendants only when acting as container PID one."""
        if os.getpid() != 1:
            return
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
            except ChildProcessError:
                break

    def run_child(
        self, command: Sequence[str], env: Mapping[str, str] | None = None
    ) -> int:
        """Wait for one owned child while honoring termination requests."""
        child = self.spawn(command, env)
        while child.poll() is None:
            if self.stopping:
                raise InterruptedError(128 + (self.signal_number or signal.SIGTERM))
            self._sleep(0.05)
        return child.wait()


def connect_wayland(env: Mapping[str, str]) -> socket.socket:
    """Return an owned connection before privilege drop without chmodding Wolf."""
    display = env.get("WAYLAND_DISPLAY")
    if not display:
        fail("Wolf WAYLAND_DISPLAY is missing")
    path = Path(env["XDG_RUNTIME_DIR"]) / display
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(5)
        connection.connect(str(path))
        # The C socket method accepts its blocking flag positionally only.
        connection.setblocking(True)  # noqa: FBT003
    except OSError:
        connection.close()
        raise
    else:
        return connection


def _write_session_log(log: TextIO, path: Path) -> None:
    """Flush the owned bridge log after its processes have finished."""
    log.flush()
    sys.stderr.write(path.read_text(encoding="utf-8") + "\n")


class Session(ProcessSupervisor):
    """Own an authenticated app-user display session and all its child groups."""

    def run(self, command: Sequence[str], env: Mapping[str, str]) -> int:
        """Run the frontend and clean up even when display setup fails.

        WAYLAND_SOCKET transfers ownership of the inherited connected descriptor.
        The environment and process-factory resources remain borrowed.
        """
        with ExitStack() as cleanup:
            wayland_fd = (
                numeric(env["WAYLAND_SOCKET"], "WAYLAND_SOCKET")
                if "WAYLAND_SOCKET" in env
                else None
            )
            if wayland_fd is not None:
                cleanup.callback(os.close, wayland_fd)
            try:
                return self._run(command, env, cleanup, wayland_fd)
            finally:
                # ES needs its own shutdown grace before its parent escalates.
                self.close(grace=6)

    def _run(
        self,
        command: Sequence[str],
        env: Mapping[str, str],
        cleanup: ExitStack,
        wayland_fd: int | None,
    ) -> int:
        self.install_signals()
        runtime = Path(env["GOW_CHILD_RUNTIME"])
        bridge_env, app_env = nvidia_environments(env, runtime)
        require_alsa_pulse()
        normalize_audio(app_env)
        resolution = _session_resolution(env)
        cookie = runtime / "Xauthority"
        cookie.touch(mode=0o600, exist_ok=False)
        cleanup.callback(cookie.unlink, missing_ok=True)
        # GOW_XAUTH is the explicitly selected bridge executable, never shell text.
        subprocess.run(  # noqa: S603
            [
                env["GOW_XAUTH"],
                "-f",
                str(cookie),
                "add",
                ":0",
                ".",
                secrets.token_hex(16),
            ],
            check=True,
            timeout=5,
        )
        bridge_env["XAUTHORITY"] = str(cookie)
        log = cleanup.enter_context(
            (runtime / "xwayland.log").open("w", encoding="utf-8")
        )
        cleanup.callback(_write_session_log, log, runtime / "xwayland.log")
        try:
            bridge = self.spawn(
                [
                    env["GOW_XWAYLAND"],
                    ":0",
                    "-noreset",
                    "-fullscreen",
                    "-geometry",
                    resolution,
                    "-nolisten",
                    "tcp",
                    "-auth",
                    str(cookie),
                ],
                bridge_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                pass_fds=() if wayland_fd is None else (wayland_fd,),
            )
            app_env.update(
                DISPLAY=":0",
                XAUTHORITY=str(cookie),
                HOME="/userdata/system",
                XDG_SESSION_TYPE="x11",
                SDL_VIDEODRIVER="x11",
                SDL_VIDEO_DRIVER="x11",
                QT_QPA_PLATFORM="xcb",
                XDG_RUNTIME_DIR=str(runtime),
            )
            for name in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET", "SWAYSOCK"):
                app_env.pop(name, None)
            self._wait_for_display(bridge, app_env)
            # Stock configgen queries the primary RandR output, not screen size.
            # Only stock output selection is requested in this owned container.
            subprocess.run(  # noqa: S603
                [_executable("batocera-resolution"), "setOutput", "auto"],
                env=app_env,
                check=True,
                timeout=10,
            )
            bus = runtime / "bus"
            app_env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + str(bus)
            dbus = self.spawn(
                [
                    "dbus-daemon",
                    "--session",
                    "--nofork",
                    "--address=" + app_env["DBUS_SESSION_BUS_ADDRESS"],
                ],
                app_env,
            )
            deadline = self._monotonic() + 5
            while not bus.exists():
                self.check([bridge, dbus])
                if self._monotonic() > deadline:
                    fail("D-Bus readiness timed out")
                self._sleep(0.05)
            openbox = self.spawn(
                ["openbox", "--config-file", "/etc/openbox/rc.xml"], app_env
            )
            hotkeys = self.spawn(
                [sys.executable, str(HERE / "runtime.py"), "hotkeys"], app_env
            )
            deadline = self._monotonic() + 5
            while True:
                self.check([bridge, dbus, openbox, hotkeys])
                status = Path(f"/proc/{hotkeys.pid}/status").read_text(encoding="utf-8")
                if any(
                    line.startswith("SigCgt:")
                    and int(line.split()[1], 16) & (1 << (signal.SIGHUP - 1))
                    for line in status.splitlines()
                ):
                    break
                if self._monotonic() >= deadline:
                    fail("hotkeygen reload-handler readiness timed out")
                self._sleep(0.05)
            # Keep the stock hotkey context command and its unchanged arguments.
            subprocess.run(  # noqa: S603
                [_executable("hotkeygen"), "--default-context"],
                env=app_env,
                check=True,
                timeout=5,
            )
            frontend = self.spawn(command, app_env)
            while frontend.poll() is None:
                self.check([bridge, dbus, openbox, hotkeys])
                self._sleep(0.05)
            return frontend.wait()
        finally:
            log.flush()
            # The cleanup stack emits the complete log after owned children stop.

    def _wait_for_display(
        self, bridge: subprocess.Popen[bytes], app_env: Mapping[str, str]
    ) -> None:
        """Require authenticated X11 access before starting stock consumers."""
        deadline = self._monotonic() + 10
        while True:
            self.check([bridge])
            try:
                # This read-only stock probe receives only the authenticated env.
                probe = subprocess.run(  # noqa: S603
                    [_executable("xset"), "q"],
                    env=app_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=min(1, max(0.01, deadline - self._monotonic())),
                )
                if probe.returncode == 0:
                    break
            except subprocess.TimeoutExpired:
                pass
            if self._monotonic() >= deadline:
                fail("authenticated Xwayland readiness timed out after ten seconds")
            self._sleep(0.05)


class Frontend(ProcessSupervisor):
    """Manage stock ES restart, suspend and quit without appliance services."""

    FLAGS = ("restart.please", "shutdown.please", "reboot.please", "suspend.please")

    def run(
        self,
        env: Mapping[str, str],
        temporary: Path = Path("/tmp"),  # noqa: S108  # Stock ES flag directory.
        command: Sequence[str] | None = None,
    ) -> int:
        """Run ES with owned children and restore the caller's working directory."""
        with ExitStack() as cleanup:
            directory = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            cleanup.callback(os.close, directory)
            cleanup.callback(os.fchdir, directory)
            try:
                return self._run(env, temporary, command, cleanup)
            finally:
                self.close()

    def _run(
        self,
        env: Mapping[str, str],
        temporary: Path,
        command: Sequence[str] | None,
        cleanup: ExitStack,
    ) -> int:
        self.install_signals()
        os.chdir("/userdata")
        if command is None:
            command = (
                "emulationstation",
                "--windowed",
                "--exit-on-reboot-required",
            )
        again = False
        if env.get("GOW_NATIVE_RESULTS"):
            ready_flag = temporary / "emulationstation.ready"
            if ready_flag.exists() or ready_flag.is_symlink():
                fail("native frontend requires a fresh private readiness flag")
            # Keep the normal frontend command and app identity. This read-only
            # observer inherits the authenticated session as an owned child.
            self.spawn(
                [sys.executable, str(HERE / "native_diagnostics.py"), "frontend"],
                env=env,
            )
        for name in self.FLAGS:
            cleanup.callback((temporary / name).unlink, missing_ok=True)
        while not self.stopping:
            # Language changes take effect on the next stock ES restart.
            # Read the stock language preference without invoking a shell.
            locale = subprocess.run(  # noqa: S603
                [_executable("batocera-settings-get"), "system.language"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            language = (locale or "en_US") + ("" if "." in locale else ".UTF-8")
            env = dict(env, LANG=language, LC_ALL=language)
            status = self.run_child(
                [*command, *(["--no-startup-game"] if again else [])], env
            )
            active = {name for name in self.FLAGS if (temporary / name).exists()}
            for name in active:
                (temporary / name).unlink()
            if active & {"shutdown.please", "reboot.please"}:
                return 0
            if "suspend.please" in active:
                self._wait_for_resume(temporary)
                again = True
                continue
            if "restart.please" not in active:
                return status
            again = True
        return 0

    def _wait_for_resume(self, temporary: Path) -> None:
        """Own the stock resume FIFO only for this suspended frontend interval."""
        fifo = temporary / "es-resume.fifo"
        if fifo.exists() or fifo.is_symlink():
            fail("conflicting resume FIFO")
        os.mkfifo(fifo, 0o600)
        try:
            descriptor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(descriptor, selectors.EVENT_READ)
                    while not self.stopping:
                        if selector.select(0.1) and os.read(descriptor, 4096):
                            break
            finally:
                os.close(descriptor)
        finally:
            fifo.unlink(missing_ok=True)
        if self.stopping:
            raise InterruptedError(128 + (self.signal_number or signal.SIGTERM))


def account(uid: int, gid: int) -> str:
    """Resolve or append runtime accounts without changing an existing identity."""
    try:
        grp.getgrgid(gid)
    except KeyError:
        name = "gowfull" + str(gid)
        try:
            grp.getgrnam(name)
            fail("runtime group name collision")
        except KeyError:
            with Path("/etc/group").open("a", encoding="utf-8") as stream:
                stream.write(f"{name}:x:{gid}:\n")
    try:
        user = pwd.getpwuid(uid)
    except KeyError:
        name = "gowfull" + str(uid)
        try:
            pwd.getpwnam(name)
            fail("runtime account name collision")
        except KeyError:
            with Path("/etc/passwd").open("a", encoding="utf-8") as stream:
                stream.write(
                    f"{name}:x:{uid}:{gid}:GoW full x86:/userdata/system:/bin/bash\n"
                )
        return name
    if user.pw_gid != gid:
        fail("existing UID has incompatible primary GID")
    return user.pw_name


def initialize_library_cache() -> None:
    """Refresh stock/injected loader discovery while preserving stock symlinks."""
    # S04populate normally builds this before Python's ctypes/PySDL2 discovery.
    # Wine replaces LD_LIBRARY_PATH, so injected driver dependencies need cache
    # entries too. Keep the stock symlinks, including other NVIDIA versions.
    directories = [
        path for path in ("/usr/nvidia/lib", "/usr/nvidia/lib32") if Path(path).is_dir()
    ]
    directories.extend(("/usr/lib", "/lib", "/lib32", "/usr/lib/mangohud"))
    # -X refreshes cache entries without modifying stock or injected symlinks.
    subprocess.run(  # noqa: S603
        ["/sbin/ldconfig", "-X", *directories], check=True, timeout=30
    )


def entrypoint(command: Sequence[str]) -> None:
    """Prepare root-owned startup and transfer the session to the app identity.

    Private transients are removed if preparation or exec fails. Successful exec
    transfers them to the disposable session container, not persistent userdata.
    """
    with ExitStack() as cleanup:
        _entrypoint(command, dict(os.environ), cleanup)


def _unlink_owned(path: Path, device: int, inode: int) -> None:
    """Remove a transient only while it still names the file this attempt made."""
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) == (device, inode):
        path.unlink()


def _remove_owned_directory(path: Path, device: int, inode: int) -> None:
    """Remove a private transient only if its original directory still exists."""
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (
        device,
        inode,
    ):
        shutil.rmtree(path)


def _entrypoint(
    command: Sequence[str], env: dict[str, str], cleanup: ExitStack
) -> None:
    uid, gid = identity(env)
    user = account(uid, gid)
    initialize_library_cache()
    # Stock mode selection otherwise promotes Xwayland's synthetic 5K mode.
    # This boot setting lives only in the container, never Wolf's saved home.
    # This boot preference is disposable container state, never mounted userdata.
    subprocess.run(  # noqa: S603
        [
            _executable("batocera-settings-set"),
            "-f",
            "/boot/batocera-boot.conf",
            "es.resolution",
            _session_resolution(env),
        ],
        check=True,
        timeout=10,
    )
    # The immutable staged launcher invokes only the maintained state initializer.
    subprocess.run([str(HERE / "init-state.sh")], env=env, check=True)  # noqa: S603
    # Wolf's shared socket runtime is never chmod/chowned. Application and bus
    # transients use a distinct private directory; Xwayland keeps the parent.
    parent = env.get("XDG_RUNTIME_DIR")
    if not parent or not Path(parent).is_absolute() or not Path(parent).is_dir():
        fail("Wolf XDG_RUNTIME_DIR is missing")
    runtime = Path(tempfile.mkdtemp(prefix="gow-full-x86-", dir="/tmp"))
    created_runtime = runtime.lstat()
    cleanup.callback(
        _remove_owned_directory, runtime, created_runtime.st_dev, created_runtime.st_ino
    )
    runtime.chmod(0o700)
    os.chown(runtime, uid, gid)
    metadata = Path("/run/gow-full-x86-session.json")
    with metadata.open("x", encoding="utf-8") as stream:
        created = os.fstat(stream.fileno())
        cleanup.callback(_unlink_owned, metadata, created.st_dev, created.st_ino)
        json.dump(
            {
                "runtime": str(runtime),
                "display": ":0",
                "xauthority": str(runtime / "Xauthority"),
                "puid": uid,
                "pgid": gid,
            },
            stream,
            sort_keys=True,
        )
        stream.write("\n")
    metadata.chmod(0o644)
    env.update(
        GOW_CHILD_RUNTIME=str(runtime), USER=user, LOGNAME=user, HOME="/userdata/system"
    )
    groups = {gid}
    for pattern in (
        "input/*",
        "hidraw*",
        "dri/*",
        "nvidia*",
        "uinput",
    ):
        for node in Path("/dev").glob(pattern):
            info = node.stat()
            if stat.S_ISCHR(info.st_mode):
                groups.add(info.st_gid)
    stock_run = Path("/var/run")
    stock_run.mkdir(parents=True, exist_ok=True)
    real_directory(stock_run)
    os.chown(stock_run, uid, gid)
    for path in (
        Path("/var/run/evmapy"),
        Path("/var/run/batocera-overlays"),
        Path("/var/run/squashfs"),
    ):
        path.mkdir(parents=True, exist_ok=True)
        real_directory(path)
        os.chown(path, uid, gid)
    for path in (Path("/var/run/evmapy/merged.keys"), Path("/var/run/hud.config")):
        if path.is_symlink():
            fail("unexpected transient symlink: " + str(path))
        path.touch(exist_ok=True)
        os.chown(path, uid, gid)
    x11 = Path("/tmp/.X11-unix")  # noqa: S108  # X11's standard socket directory.
    x11.mkdir(mode=0o1777, exist_ok=True)
    real_directory(x11)
    if x11.stat().st_uid != 0:
        fail("X11 socket directory must belong to root")
    x11.chmod(0o1777)
    # Wolf's socket can be root-owned without write access for the app UID.
    # Pass a connected descriptor to Xwayland, never loosen the shared socket.
    with connect_wayland(env) as connection:
        connection.set_inheritable(True)
        env["WAYLAND_SOCKET"] = str(connection.fileno())
        # Exec the configured privilege-drop tool, preserving argv without a shell.
        os.execve(  # noqa: S606
            env["GOW_SETPRIV"],
            [
                env["GOW_SETPRIV"],
                "--reuid",
                str(uid),
                "--regid",
                str(gid),
                "--groups",
                ",".join(map(str, sorted(groups))),
                "--",
                str(HERE / "session.sh"),
                *command,
            ],
            env,
        )


@runtime_checkable
class StockInputDevice(Protocol):
    """Stock device data needed to distinguish an absent forwarded event node."""

    @property
    def device_node(self) -> str:
        """Return the stock device's absolute event-node pathname."""
        ...


@runtime_checkable
class StockDaemon(Protocol):
    """Stock hotkey daemon lifecycle exposed by the approved loader boundary."""

    def run(self) -> None:
        """Process stock mappings and contexts until shutdown."""
        ...


@runtime_checkable
class StockDaemonFactory(Protocol):
    """Construct a stock daemon with permanent-mode processing."""

    def __call__(self, *, permanent: bool) -> StockDaemon:
        """Create a daemon whose lifetime belongs to this command."""
        ...


@runtime_checkable
class StockActionHandler(Protocol):
    """Unbound stock callback, retained unchanged except missing-node refusal."""

    def __call__(self, daemon: object, action: str, device: StockInputDevice) -> object:
        """Process one native device action."""
        ...


def run_hotkeys() -> None:
    """Load stock hotkeygen and ignore only absent forwarded input-node opens."""
    executable = shutil.which("hotkeygen")
    if executable is None:
        fail("missing stock hotkeygen executable")
    # Stock is the approved runpy boundary; project modules use normal imports.
    native = runpy.run_path(executable)
    daemon_class: object = native.get("Daemon")
    if not isinstance(daemon_class, type):
        fail("stock hotkeygen has no Daemon class")
    handler: object = getattr(daemon_class, "_Daemon__handle_actions", None)
    if not isinstance(handler, StockActionHandler):
        fail("stock hotkeygen has no device action callback")

    def handle_actions(daemon: object, action: str, device: StockInputDevice) -> object:
        try:
            return handler(daemon, action, device)
        except FileNotFoundError as error:
            if action != "add" or error.filename != device.device_node:
                raise
            sys.stdout.write(
                "gow-full-x86: ignoring unmounted input node "
                + device.device_node
                + "\n"
            )
            sys.stdout.flush()
            return None

    def namespace(values: dict[str, object]) -> None:
        values["_Daemon__handle_actions"] = handle_actions

    factory: object = new_class(
        "ContainerHotkeys", (daemon_class,), exec_body=namespace
    )
    if not isinstance(factory, StockDaemonFactory):
        fail("stock hotkeygen daemon cannot be constructed")
    daemon = factory(permanent=True)
    if not isinstance(daemon, StockDaemon):
        fail("stock hotkeygen daemon has no run method")
    daemon.run()


def _check_runtime(env: Mapping[str, str]) -> None:
    """Check stock executables, the configured bridge and staged seed support."""
    for binary in (
        "python3",
        "bash",
        "tar",
        "dbus-daemon",
        "dbus-uuidgen",
        "xset",
        "openbox",
        "hotkeygen",
        "emulationstation",
        "batocera-settings-get",
    ):
        _executable(binary)
    for name in ("GOW_XWAYLAND", "GOW_XAUTH", "GOW_SETPRIV"):
        if not os.access(env[name], os.X_OK):
            fail("missing bridge executable: " + name)
    require_alsa_pulse()
    if not (HERE / "stock-share.tar").is_file():
        fail("missing SHARE seed")
    # Request only feature/version output from the selected stock tar.
    subprocess.run(  # noqa: S603
        [_executable("tar"), "--acls", "--xattrs", "--version"],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> int:
    """Assemble runtime dependencies and translate startup failures to status."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("entrypoint", "init-state", "session", "frontend", "hotkeys", "check"),
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command: list[str] = args.command or [str(HERE / "frontend.sh")]
    try:
        if args.action == "entrypoint":
            entrypoint(command)
        elif args.action == "init-state":
            StateInitializer(*identity(os.environ)).run()
        elif args.action == "session":
            return Session(launch_process, time.monotonic, time.sleep).run(
                command, dict(os.environ)
            )
        elif args.action == "frontend":
            return Frontend(launch_process, time.monotonic, time.sleep).run(
                dict(os.environ)
            )
        elif args.action == "hotkeys":
            run_hotkeys()
        else:
            _check_runtime(os.environ)
    except InterruptedError as error:
        return error.args[0] if error.args and isinstance(error.args[0], int) else 143
    except (
        RuntimeError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
        ExceptionGroup,
    ) as error:
        sys.stderr.write("gow-full-x86: " + str(error) + "\n")
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
